"""M008a: asset generations retain old JPEGs during scan and viewer rebuild."""
from __future__ import annotations

import json
import sqlite3
import threading
import urllib.request
from pathlib import Path

import fitz
import pytest
from PIL import Image

from ppt_visual_archive import perf_metrics, pipeline
from ppt_visual_archive.agent import refresh_archive
from ppt_visual_archive.asset_generations import ImageGeneration
from ppt_visual_archive.config import default_config
from ppt_visual_archive.index_db import IndexDB
from ppt_visual_archive.server import create_server


def _pdf(path: Path, pages: int):
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=400, height=225)
        page.insert_text((45, 55), f"Version {pages}, page {i + 1}")
    doc.save(path)
    doc.close()


@pytest.fixture
def archive(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    path = root / "slides.pdf"
    _pdf(path, 1)
    cfg = default_config(str(tmp_path / "viewer"), [str(root)])
    cfg.file_types = ["pdf"]
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    assert refresh_archive(cfg)["processed_ok"] == 1
    return cfg, path


def _slides(cfg):
    db = IndexDB(cfg.db_path)
    try:
        return db.get_all_slides()
    finally:
        db.close()


def test_versioned_pdf_images_keep_previous_export_alive(archive):
    cfg, path = archive
    old = _slides(cfg)[0]
    image_path = Path(cfg.output_dir) / old.thumb_path
    assert "/v-" in old.thumb_path
    previous = image_path.read_bytes()
    previous_json = (Path(cfg.output_dir) / "data/export.json").read_bytes()

    _pdf(path, 2)
    # The scan updates SQL but does not rebuild JSON yet.
    assert pipeline.run_scan(cfg)["processed_ok"] == 1
    new = _slides(cfg)
    assert len(new) == 2
    assert new[0].thumb_path != old.thumb_path
    assert previous_json == (Path(cfg.output_dir) / "data/export.json").read_bytes()
    assert image_path.read_bytes() == previous
    assert (Path(cfg.output_dir) / new[0].thumb_path).is_file()

    summary = refresh_archive(cfg)
    assert summary["viewer_rebuilt"] is True
    assert image_path.read_bytes() == previous
    published = json.loads((Path(cfg.output_dir) / "data/export.json").read_text())
    assert published["stats"]["slide_count"] == 2
    assert published["slides"][0]["thumb"] != old.thumb_path


def test_corrupt_pdf_or_missing_image_keeps_old_generation(archive, monkeypatch):
    cfg, path = archive
    old = _slides(cfg)[0]
    old_image = (Path(cfg.output_dir) / old.thumb_path).read_bytes()

    path.write_bytes(b"not a PDF")
    summary = refresh_archive(cfg)
    assert summary["processed_err"] == 1
    assert _slides(cfg)[0].thumb_path == old.thumb_path
    assert (Path(cfg.output_dir) / old.thumb_path).read_bytes() == old_image

    _pdf(path, 3)
    original = pipeline.extract_and_render_pdf

    def broken(pdf_path, output_dir, render):
        payload = original(pdf_path, output_dir, render)
        (Path(output_dir) / payload["slides"][1]["thumb_path"]).unlink()
        return payload

    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "extract_and_render_pdf", broken)
        summary = refresh_archive(cfg)
        assert summary["processed_err"] == 1
    assert _slides(cfg)[0].thumb_path == old.thumb_path
    assets = Path(cfg.output_dir) / "assets" / "decks"
    assert not list(assets.rglob(".render-*"))
    assert len(list(assets.rglob("v-*"))) == 1


def test_sql_failure_discards_only_new_generation(archive, monkeypatch):
    cfg, path = archive
    old = _slides(cfg)[0]
    old_image = (Path(cfg.output_dir) / old.thumb_path).read_bytes()
    _pdf(path, 2)
    prior = IndexDB.replace_deck_and_slides

    def fail_new_deck(db, deck, slides):
        if deck.slide_count == 2:
            raise sqlite3.OperationalError("injected disk failure")
        return prior(db, deck, slides)

    monkeypatch.setattr(IndexDB, "replace_deck_and_slides", fail_new_deck)
    with pytest.raises(sqlite3.OperationalError):
        pipeline.run_scan(cfg)
    assert _slides(cfg)[0].thumb_path == old.thumb_path
    assert (Path(cfg.output_dir) / old.thumb_path).read_bytes() == old_image
    assets = Path(cfg.output_dir) / "assets" / "decks"
    assert not list(assets.rglob(".render-*"))
    assert len(list(assets.rglob("v-*"))) == 1


def test_deleted_deck_preserves_old_images_until_explicit_cleanup(archive):
    cfg, source = archive
    old = _slides(cfg)[0]
    prior = Path(cfg.output_dir) / old.thumb_path
    source.unlink()
    assert refresh_archive(cfg)["deleted"] == 1
    assert _slides(cfg) == []
    assert prior.is_file()  # Existing browser tab may still reference it


def test_active_http_reader_uses_previous_images_during_refresh(archive):
    cfg, path = archive
    old_path = _slides(cfg)[0].thumb_path
    image = (Path(cfg.output_dir) / old_path).read_bytes()
    server = create_server(cfg.output_dir, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _pdf(path, 2)
        assert pipeline.run_scan(cfg)["processed_ok"] == 1
        with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/{old_path}") as response:
            assert response.read() == image
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_generation_disallows_unsafe_paths_and_duplicate_numbers(tmp_path):
    with ImageGeneration(tmp_path, "deck") as generation:
        Image.new("RGB", (25, 25)).save(generation.stage / "thumb.jpg")
        Image.new("RGB", (25, 25)).save(generation.stage / "preview.jpg")
        with pytest.raises(RuntimeError, match="invalid"):
            generation.validate([{
                "slide_number": 1, "thumb_path": "../private.jpg", "preview_path": "preview.jpg",
            }])
        with pytest.raises(RuntimeError, match="duplicate"):
            generation.validate([{
                "slide_number": 1, "thumb_path": "thumb.jpg", "preview_path": "preview.jpg",
            }, {
                "slide_number": 1, "thumb_path": "thumb.jpg", "preview_path": "preview.jpg",
            }])
    assert not list((tmp_path / "assets").rglob(".render-*"))


def test_powerpoint_images_are_versioned_without_overwriting_prior_render(tmp_path, monkeypatch):
    """PPTX metadata comes from original; any renderer uses immutable image paths."""
    from pptx import Presentation

    root = tmp_path / "presentations"
    root.mkdir()
    source = root / "deck.pptx"

    def save_pptx(slide_count):
        pres = Presentation()
        for n in range(slide_count):
            slide = pres.slides.add_slide(pres.slide_layouts[0])
            slide.shapes.title.text = f"Original PPTX title {n + 1}"
            slide.notes_slide.notes_text_frame.text = f"Original note {n + 1}"
        pres.save(source)

    save_pptx(1)
    cfg = default_config(str(tmp_path / "archive"), [str(root)])
    cfg.file_types = ["pptx"]
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")

    class FakeWindowsOrMacRenderer:
        def start(self): pass
        def stop(self): pass

        def export_slides(self, path, output_dir):
            pres = Presentation(path)
            produced = []
            for number, _ in enumerate(pres.slides, 1):
                thumb = f"thumb_{number:03d}.jpg"
                preview = f"preview_{number:03d}.jpg"
                color = (30 + number * 35, 100, 130)
                for name in (thumb, preview):
                    Image.new("RGB", (120, 68), color).save(Path(output_dir) / name)
                produced.append({
                    "slide_number": number, "thumb_path": thumb,
                    "preview_path": preview, "width": 120, "height": 68,
                })
            return produced

    monkeypatch.setattr(pipeline, "create_pptx_renderer", lambda _: FakeWindowsOrMacRenderer())
    first = refresh_archive(cfg)
    assert first["processed_ok"] == 1
    old = _slides(cfg)[0]
    bytes_before = (Path(cfg.output_dir) / old.thumb_path).read_bytes()

    save_pptx(2)
    second = refresh_archive(cfg)
    assert second["changed"] == 1 and second["processed_ok"] == 1
    updated = _slides(cfg)
    assert len(updated) == 2
    assert updated[0].thumb_path != old.thumb_path
    assert updated[0].title == "Original PPTX title 1"
    assert "Original note" in updated[0].notes_text
    assert (Path(cfg.output_dir) / old.thumb_path).read_bytes() == bytes_before
    assert (Path(cfg.output_dir) / updated[1].preview_path).is_file()
