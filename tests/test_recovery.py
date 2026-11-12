"""M007e recovery tests: unavailable roots, malformed documents, partial DB work."""
from __future__ import annotations

import errno
import json
import os
import sqlite3
from pathlib import Path

import fitz
import pytest

from ppt_visual_archive import builder, perf_metrics, scanner
from ppt_visual_archive.agent import refresh_archive
from ppt_visual_archive.config import default_config
from ppt_visual_archive.index_db import IndexDB
from ppt_visual_archive.models import Deck, Slide
from ppt_visual_archive.pipeline import run_scan


def create_pdf(path: Path, pages: int = 1):
    doc = fitz.open()
    for i in range(pages):
        doc.new_page().insert_text((60, 60), f"Valid document page {i}")
    doc.save(path)
    doc.close()


@pytest.fixture
def indexed_archive(tmp_path, monkeypatch):
    roots = [tmp_path / "library-one", tmp_path / "library-two"]
    for root in roots:
        root.mkdir()
    pdf = roots[0] / "presentation.pdf"
    create_pdf(pdf)
    config = default_config(str(tmp_path / "viewer"), [str(root) for root in roots])
    config.file_types = ["pdf"]
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    assert refresh_archive(config)["processed_ok"] == 1
    assert builder.viewer_is_current(config)
    return config, pdf, roots


def snapshot(config):
    db = IndexDB(config.db_path)
    try:
        return {
            "decks": [(d.deck_id, d.file_signature, d.slide_count) for d in db.get_all_active_decks()],
            "slides": [(s.slide_id, s.title) for s in db.get_all_slides()],
        }
    finally:
        db.close()


def test_missing_scan_root_does_not_delete_archive(indexed_archive):
    config, pdf, roots = indexed_archive
    before = snapshot(config)
    original_json = (Path(config.output_dir) / "data/export.json").read_bytes()
    roots[1].rmdir()  # Simulate an unavailable network share or external drive.
    with pytest.raises(FileNotFoundError, match="Scan root unavailable"):
        refresh_archive(config)
    assert snapshot(config) == before
    assert (Path(config.output_dir) / "data/export.json").read_bytes() == original_json
    assert builder.viewer_is_current(config)


def test_partial_directory_access_failure_aborts_without_deletion(indexed_archive, monkeypatch):
    config, pdf, roots = indexed_archive
    before = snapshot(config)
    actual_walk = scanner.os.walk

    def inaccessible_walk(path, *args, **kwargs):
        if str(path) == str(roots[1]):
            kwargs["onerror"](PermissionError(errno.EACCES, "Permission denied", str(path)))
        yield from actual_walk(path, *args, **kwargs)

    monkeypatch.setattr(scanner.os, "walk", inaccessible_walk)
    with pytest.raises(PermissionError):
        refresh_archive(config)
    assert snapshot(config) == before


def test_transient_stat_error_aborts_without_deletion(indexed_archive, monkeypatch):
    config, pdf, roots = indexed_archive
    before = snapshot(config)
    original_stat = os.stat

    def fail_specific_stat(path, *args, **kwargs):
        if str(path) == str(pdf):
            raise OSError(errno.EIO, "Transient drive I/O failure", str(path))
        return original_stat(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(scanner.os, "stat", fail_specific_stat)
        with pytest.raises(OSError, match="I/O failure"):
            refresh_archive(config)
    assert snapshot(config) == before


def test_invalid_changed_pdf_preserves_prior_deck_and_recovers(indexed_archive):
    config, pdf, roots = indexed_archive
    before = snapshot(config)
    prior_images = sorted((Path(config.output_dir) / "assets").rglob("*.jpg"))
    pdf.write_bytes(b"not a valid PDF, corrupt replacement data")
    failed = refresh_archive(config)
    assert failed["changed"] == 1
    assert failed["processed_err"] == 1
    assert failed["processed_ok"] == 0
    assert snapshot(config) == before
    assert builder.viewer_is_current(config)
    assert all(item.exists() for item in prior_images)

    create_pdf(pdf, pages=2)
    repaired = refresh_archive(config)
    assert repaired["changed"] == 1 and repaired["processed_ok"] == 1
    after = snapshot(config)
    assert after["decks"][0][2] == 2
    assert len(after["slides"]) == 2
    assert builder.viewer_is_current(config)


def test_atomic_deck_replacement_rolls_back_after_invalid_slide(tmp_path):
    db = IndexDB(tmp_path / "index.db")
    base = Deck(
        deck_id="d", file_path="/slides/a.pdf", file_name="a.pdf",
        folder_path="/slides", file_size=5, modified_time=10, processed_time=10,
        file_signature="old", slide_count=1,
    )
    try:
        db.replace_deck_and_slides(base, [Slide(slide_id="d_s1", deck_id="d", slide_number=1, title="Original")])
        changed = Deck(
            deck_id="d", file_path="/slides/a.pdf", file_name="a.pdf",
            folder_path="/slides", file_size=10, modified_time=20, processed_time=20,
            file_signature="new", slide_count=2,
        )
        # Duplicate primary key ensures INSERT fails after old slides are
        # deleted inside the transaction, proving rollback restores the old set.
        duplicated = [
            Slide(slide_id="d_dup", deck_id="d", slide_number=1),
            Slide(slide_id="d_dup", deck_id="d", slide_number=2),
        ]
        with pytest.raises(sqlite3.IntegrityError):
            db.replace_deck_and_slides(changed, duplicated)
        assert db.get_deck("d").file_signature == "old"
        assert [(s.slide_id, s.title) for s in db.get_slides_for_deck("d")] == [("d_s1", "Original")]
    finally:
        db.close()


def test_crash_after_sqlite_commit_before_viewer_build_is_repaired(indexed_archive):
    config, pdf, roots = indexed_archive
    before = json.loads((Path(config.output_dir) / "data/export.json").read_text())
    assert before["stats"]["slide_count"] == 1

    create_pdf(pdf, pages=2)
    # Simulate process termination after index commit, before build_viewer.
    summary = run_scan(config)
    assert summary["changed"] == 1 and summary["processed_ok"] == 1
    assert builder.viewer_is_current(config) is False
    old_export = json.loads((Path(config.output_dir) / "data/export.json").read_text())
    assert old_export["stats"]["slide_count"] == 1

    # Filesystem scan now sees no changes, but DB fingerprint forces publication.
    recovered = refresh_archive(config)
    assert recovered["new"] == recovered["changed"] == recovered["deleted"] == 0
    assert recovered["viewer_rebuilt"] is True
    assert builder.viewer_is_current(config)
    new_export = json.loads((Path(config.output_dir) / "data/export.json").read_text())
    assert new_export["stats"]["slide_count"] == 2


def test_disk_full_during_publication_preserves_existing_export_and_repairs(indexed_archive, monkeypatch):
    config, pdf, roots = indexed_archive
    old_json = (Path(config.output_dir) / "data/export.json").read_bytes()
    original_replace = builder._replace_published_file

    def no_space(staged, destination):
        if destination.name == "export.json":
            raise OSError(errno.ENOSPC, "No space left on device")
        return original_replace(staged, destination)

    with monkeypatch.context() as patch:
        patch.setattr(builder, "_replace_published_file", no_space)
        with pytest.raises(OSError) as failure:
            builder.build_viewer(config)
    assert failure.value.errno == errno.ENOSPC
    assert (Path(config.output_dir) / "data/export.json").read_bytes() == old_json
    assert builder.viewer_is_current(config) is False

    fixed = refresh_archive(config)
    assert fixed["viewer_rebuilt"] is True
    assert builder.viewer_is_current(config)
