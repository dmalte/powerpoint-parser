"""Scanner regression for one vanished file among otherwise valid documents."""
from __future__ import annotations

import errno
from pathlib import Path

import fitz
import pytest

from ppt_visual_archive import perf_metrics, scanner
from ppt_visual_archive.agent import refresh_archive
from ppt_visual_archive.config import default_config
from ppt_visual_archive.index_db import IndexDB


def _pdf(path: Path, content: str) -> None:
    doc = fitz.open()
    doc.new_page().insert_text((70, 70), content)
    doc.save(path)
    doc.close()


def test_vanished_file_during_discovery_does_not_abort_or_delete_old_deck(tmp_path, monkeypatch):
    source = tmp_path / "documents"
    source.mkdir()
    _pdf(source / "present.pdf", "Older document")
    missing = source / "temporarily-unavailable.pdf"
    _pdf(missing, "Previously indexed")
    config = default_config(str(tmp_path / "viewer"), [str(source)])
    config.file_types = ["pdf"]
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    first = refresh_archive(config)
    assert first["processed_ok"] == 2
    missing.unlink()
    _pdf(source / "new.pdf", "New document")
    original_walk = scanner.os.walk

    def stale_walk(path, *args, **kwargs):
        if str(path) == str(source):
            yield str(source), [], ["present.pdf", "temporarily-unavailable.pdf", "new.pdf"]
        else:
            yield from original_walk(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(scanner.os, "walk", stale_walk)
        incomplete = refresh_archive(config)
    assert incomplete["processed_ok"] == 1
    assert incomplete["skipped_missing"] == 1
    assert incomplete["discovery_complete"] is False
    assert incomplete["deleted"] == 0
    db = IndexDB(config.db_path)
    try:
        assert len(db.get_all_active_decks()) == 3
    finally:
        db.close()

    # A later complete pass is allowed to infer the true deletion.
    complete = refresh_archive(config)
    assert complete["deleted"] == 1
    assert "skipped_missing" not in complete
    db = IndexDB(config.db_path)
    try:
        assert len(db.get_all_active_decks()) == 2
    finally:
        db.close()


def test_dangling_symlink_is_skipped_without_exposing_external_target(tmp_path, monkeypatch):
    src = tmp_path / "source"
    src.mkdir()
    good = src / "keep.md"
    good.write_text("# Working\n\nSafe record", encoding="utf-8")
    link = src / "bad.md"
    try:
        link.symlink_to(tmp_path / "missing-external.md")
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable on this filesystem")
    config = default_config(str(tmp_path / "archive"), [str(src)])
    config.file_types = ["md"]
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    done = refresh_archive(config)
    assert done["skipped_missing"] == 1
    assert done["processed_ok"] == 1
    assert done["deleted"] == 0
    db = IndexDB(config.db_path)
    try:
        assert len(db.get_all_active_decks()) == 1
    finally:
        db.close()


def test_transient_permission_error_still_aborts_and_preserves_prior_records(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    first = source / "first.md"
    first.write_text("# First", encoding="utf-8")
    config = default_config(str(tmp_path / "archive"), [str(source)])
    config.file_types = ["md"]
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    assert refresh_archive(config)["processed_ok"] == 1
    real_stat = scanner.os.stat

    def denied(path, *args, **kwargs):
        if str(path) == str(first):
            raise PermissionError(errno.EACCES, "Permission denied", str(first))
        return real_stat(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(scanner.os, "stat", denied)
        with pytest.raises(PermissionError):
            refresh_archive(config)
    db = IndexDB(config.db_path)
    try:
        assert len(db.get_all_active_decks()) == 1
    finally:
        db.close()
