"""M012: first-page US Letter Markdown images, secure full-text indexing and recovery."""
from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

import fitz
import pytest
from PIL import Image

from ppt_visual_archive import perf_metrics
from ppt_visual_archive.agent import AgentRuntime, refresh_archive
from ppt_visual_archive.builder import viewer_is_current
from ppt_visual_archive.config import default_config, load_config, save_config
from ppt_visual_archive.index_db import IndexDB
from ppt_visual_archive.markdown_processor import (
    LETTER_PREVIEW_PIXELS, LETTER_THUMB_PIXELS, MAX_SOURCE_BYTES,
    _parser, render_markdown_snippets,
)
from ppt_visual_archive.pipeline import run_scan
from ppt_visual_archive.server import create_server


@pytest.fixture(autouse=True)
def _local_metrics(monkeypatch, tmp_path):
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "metrics")


def _config(tmp_path, *, types=None):
    files = tmp_path / "inputs"
    files.mkdir()
    config = default_config(str(tmp_path / "viewer"), [str(files)])
    config.file_types = types or ["md"]
    return config, files


def _pdf(path, phrase="PDF page"):
    doc = fitz.open()
    doc.new_page(width=720, height=405).insert_text((80, 80), phrase)
    doc.save(path)
    doc.close()


def _data(config):
    return json.loads((Path(config.output_dir) / "data/export.json").read_text(encoding="utf-8"))


def test_one_letter_page_ignores_all_heading_boundaries_and_frontmatter(tmp_path):
    tick = chr(96)
    source = tmp_path / "notes.md"
    source.write_text(
        "---\ntags: [internal]\n---\nIntro paragraph.\n\n# Overview\n"
        "Normal text.\n" + tick * 3 + "markdown\n# Not a heading\n" + tick * 3
        + "\n\n## Details\nA paragraph.\n\n"
        + "~~~python\n## Also not a heading\n~~~\n"
        + "\n### Third\nMore text.", encoding="utf-8"
    )
    rendered = render_markdown_snippets(source, tmp_path / "out")
    assert len(rendered) == 1
    record = rendered[0]
    assert record["slide_number"] == 1 and record["title"] == "notes"
    for value in ("Intro paragraph", "Overview", "Not a heading", "Details", "Third"):
        assert value in record["extracted_text"]
    assert "tags:" not in record["extracted_text"]
    assert record["width"] == 816 and record["height"] == 1056
    with Image.open(tmp_path / "out" / record["preview_path"]) as page:
        assert page.size == LETTER_PREVIEW_PIXELS and page.format == "JPEG"
    with Image.open(tmp_path / "out" / record["thumb_path"]) as thumb:
        assert thumb.size == LETTER_THUMB_PIXELS and thumb.format == "JPEG"


def test_long_markdown_has_one_page_but_full_document_is_searchable(tmp_path):
    source = tmp_path / "long-note.md"
    beginning = "\n\n".join("First-page paragraph with normal words. " * 25 for _ in range(45))
    source.write_text(beginning, encoding="utf-8")
    first = render_markdown_snippets(source, tmp_path / "before")[0]
    # This extra paragraph is far beyond the Letter page; it remains indexed
    # but cannot change the actual pixels laid out on the first page.
    source.write_text(beginning + "\n\n## Very late section\nLATE_DOCUMENT_SEARCH_SENTINEL", encoding="utf-8")
    second = render_markdown_snippets(source, tmp_path / "after")[0]
    assert "LATE_DOCUMENT_SEARCH_SENTINEL" in second["extracted_text"]
    assert len([p for p in (tmp_path / "after").glob("preview*.jpg")]) == 1
    with Image.open(tmp_path / "before" / first["preview_path"]) as one, Image.open(tmp_path / "after" / second["preview_path"]) as two:
        assert one.size == two.size == LETTER_PREVIEW_PIXELS
        assert one.tobytes() == two.tobytes()  # only first Letter page visible


def test_letter_page_renders_rich_markdown_without_active_html(tmp_path):
    source = tmp_path / "Untrusted Notes.md"
    tick = chr(96)
    original = (
        "---\ntitle: private\n---\n# Security & Data\n"
        "Bold **value** and *emphasis* and [link](https://bad.example/track?key=secret).\n\n"
        "<script>window.alert('unsafe')</script>\n"
        "<img src=x onerror=alert(1)>\n\n"
        "![remote image](https://bad.example/exfil.png)\n\n"
        "| Field | Value |\n|---|---|\n| Rate | 10% |\n\n"
        + tick * 3 + "python\nprint('safe code')\n" + tick * 3 + "\n"
    )
    source.write_text(original, encoding="utf-8")
    before = source.read_bytes()
    records = render_markdown_snippets(source, tmp_path / "generated")
    assert source.read_bytes() == before and len(records) == 1
    record = records[0]
    assert "Security & Data" in record["extracted_text"]
    assert "Rate" in record["extracted_text"] and "value" in record["extracted_text"]
    assert "safe code" in record["extracted_text"]
    assert "title: private" not in record["extracted_text"]
    assert record["preview_path"].endswith(".jpg")
    assert not list((tmp_path / "generated").glob("*.html"))
    assert not list((tmp_path / "generated").glob("local_image_*"))
    with Image.open(tmp_path / "generated" / record["preview_path"]) as page:
        page.verify()
    with Image.open(tmp_path / "generated" / record["thumb_path"]) as image:
        assert image.size == LETTER_THUMB_PIXELS and image.format == "JPEG"


def test_commonmark_heading_and_table_parser_is_available():
    parser = _parser()
    output = parser.render("# Title\n\n> Quote\n\n| A | B |\n|---|---|\n| 1 | 2 |")
    assert "<h1>Title</h1>" in output
    assert "<blockquote>" in output
    assert "<table>" in output


def test_markdown_incremental_index_and_browsable_viewer(tmp_path):
    config, root = _config(tmp_path)
    source = root / "my note.md"
    source.write_text("# Heading One\n\nFirst sentence.\n\n## Heading Two\n\nSecond **bold** sentence.", encoding="utf-8")
    before = source.read_bytes()
    first = refresh_archive(config)
    assert first["new"] == 1 and first["processed_ok"] == 1
    assert first["viewer_rebuilt"] is True
    assert source.read_bytes() == before

    deck = _data(config)
    assert deck["stats"]["deck_count"] == 1
    assert deck["stats"]["slide_count"] == 1
    assert len(deck["slides"]) == 1
    assert deck["slides"][0]["title"] == "my note"
    assert "Heading One" in deck["slides"][0]["body"]
    assert "Second bold sentence" in deck["slides"][0]["body"]
    assets = Path(config.output_dir)
    for slide in deck["slides"]:
        assert slide["preview"].endswith(".jpg")
        assert slide["thumb"].endswith(".jpg")
        assert (assets / slide["preview"]).is_file()
        assert (assets / slide["thumb"]).is_file()

    unchanged = refresh_archive(config)
    assert unchanged["unchanged"] == 1
    assert unchanged["viewer_rebuilt"] is False


def test_markdown_updates_publish_new_generation_and_preserve_prior_browsing(tmp_path):
    config, root = _config(tmp_path)
    path = root / "record.md"
    path.write_text("# Initial\n\nText 1.", encoding="utf-8")
    assert refresh_archive(config)["processed_ok"] == 1
    previous = _data(config)["slides"][0]
    prior_html = Path(config.output_dir) / previous["preview"]
    prior_thumb = Path(config.output_dir) / previous["thumb"]
    original_bytes = prior_html.read_bytes()

    path.write_text("# Initial\n\nText 1 expanded.\n\n## New section\n\nText 2.", encoding="utf-8")
    updated = refresh_archive(config)
    assert updated["changed"] == 1 and updated["processed_ok"] == 1
    slides = _data(config)["slides"]
    assert len(slides) == 1
    assert slides[0]["preview"] != previous["preview"]
    assert "New section" in slides[0]["body"]
    assert prior_html.read_bytes() == original_bytes
    assert prior_thumb.is_file()
    assert viewer_is_current(config)


def test_markdown_signature_migration_replaces_legacy_sections_incrementally(tmp_path):
    config, root = _config(tmp_path, types=["pdf", "md"])
    document = root / "legacy.md"
    document.write_text("# Old heading\n\nOne.\n\n## Old second heading\n\nTwo.")
    _pdf(root / "unchanged.pdf")
    first = refresh_archive(config)
    assert first["processed_ok"] == 2
    export = _data(config)
    old_md = next(row for row in export["decks"] if row["file_name"] == "legacy.md")
    assert old_md["slide_count"] == 1
    old_image = next(s for s in export["slides"] if s["deck_id"] == old_md["id"])
    old_preview = Path(config.output_dir) / old_image["preview"]
    original_bytes = old_preview.read_bytes()
    source_bytes = document.read_bytes()

    # Simulate a two-section legacy index. The next successful refresh must
    # replace both old rows with one, not leave orphan heading snippets.
    from ppt_visual_archive.models import Slide
    db = IndexDB(config.db_path)
    try:
        deck = next(d for d in db.get_all_active_decks() if d.deck_id == old_md["id"])
        assert deck.file_signature.endswith("|markdown-letter-page-v1|markdown-https-auto-v2")
        deck.file_signature = deck.file_signature.replace(
            "|markdown-letter-page-v1|markdown-https-auto-v2",
            "|markdown-local-images-v1",
        )
        deck.slide_count = 2
        original = next(s for s in db.get_all_slides() if s.deck_id == deck.deck_id)
        additional = Slide(
            slide_id=deck.deck_id + "_s002", deck_id=deck.deck_id,
            slide_number=2, title="Legacy second section", body_text="Two",
            extracted_text="Old second heading Two", thumb_path=original.thumb_path,
            preview_path=original.preview_path,
        )
        db.replace_deck_and_slides(deck, [original, additional])
        assert len([s for s in db.get_all_slides() if s.deck_id == deck.deck_id]) == 2
    finally:
        db.close()
    updated = refresh_archive(config)
    assert updated["processed_ok"] == 1 and updated["changed"] == 1
    assert updated["unchanged"] == 1  # PDF never re-rendered
    assert _data(config)["stats"]["slide_count"] == 2
    new_image = next(s for s in _data(config)["slides"] if s["deck_id"] == old_md["id"])
    assert new_image["preview"] != old_image["preview"]
    assert old_preview.read_bytes() == original_bytes
    assert document.read_bytes() == source_bytes
    assert refresh_archive(config)["viewer_rebuilt"] is False


def test_full_document_text_after_first_page_is_indexed_in_sqlite(tmp_path):
    cfg, root = _config(tmp_path)
    (root / "long.md").write_text(
        "# Letter document\n\n" + ("A lot of words " * 80 + "\n\n") * 40
        + "## Later heading\n\nSEARCHABLE_BEYOND_FIRST_PAGE"
    )
    assert refresh_archive(cfg)["processed_ok"] == 1
    assert _data(cfg)["stats"]["slide_count"] == 1
    with_db = IndexDB(cfg.db_path)
    try:
        matched = with_db.search_slides("SEARCHABLE_BEYOND_FIRST_PAGE")
        assert len(matched) == 1
        assert "Later heading" in matched[0].extracted_text
    finally:
        with_db.close()


def test_legacy_html_asset_remains_browseable_with_inert_csp(tmp_path):
    from ppt_visual_archive.server import create_server
    archive = tmp_path / "archive"
    old = archive / "assets/decks/legacy/v-old/preview_001.html"
    old.parent.mkdir(parents=True)
    old.write_text("<h1>Legacy heading</h1><p>Old archived preview</p>")
    server = create_server(str(archive), 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/assets/decks/legacy/v-old/preview_001.html", timeout=3
        ) as response:
            assert response.status == 200
            assert "Legacy heading" in response.read().decode()
            assert "script-src 'none'" in response.headers["Content-Security-Policy"]
            assert response.headers["X-Content-Type-Options"] == "nosniff"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_corrupt_markdown_change_preserves_previous_db_and_assets(tmp_path):
    config, root = _config(tmp_path)
    path = root / "draft.md"
    path.write_text("# Valid\n\nOriginal", encoding="utf-8")
    assert refresh_archive(config)["processed_ok"] == 1
    prior = _data(config)
    original_index = (Path(config.output_dir) / "data/export.json").read_bytes()
    path.write_bytes(b"\xff\xfe\xfa malformed unicode")
    failed = refresh_archive(config)
    assert failed["processed_err"] == 1
    assert failed["processed_ok"] == 0
    assert (Path(config.output_dir) / "data/export.json").read_bytes() == original_index
    assert (Path(config.output_dir) / prior["slides"][0]["thumb"]).is_file()
    assert viewer_is_current(config)
    db = IndexDB(config.db_path)
    try:
        assert db.get_all_slides()[0].title == "draft"
    finally:
        db.close()


def test_mixed_pdf_and_markdown_share_index_and_search(tmp_path):
    config, root = _config(tmp_path, types=["pdf", "md"])
    _pdf(root / "report.pdf", "Quarterly revenue")
    (root / "plan.md").write_text("# Direction\n\nA Markdown **roadmap** document.", encoding="utf-8")
    summary = refresh_archive(config)
    assert summary["processed_ok"] == 2
    export = _data(config)
    assert export["stats"]["deck_count"] == 2
    assert export["stats"]["slide_count"] == 2
    assert {Path(d["file_name"]).suffix for d in export["decks"]} == {".pdf", ".md"}
    db = IndexDB(config.db_path)
    try:
        assert len(db.search_slides("roadmap")) == 1
        assert len(db.search_slides("Quarterly")) >= 1
    finally:
        db.close()


def test_markdown_can_pause_between_files_and_resume_safely(tmp_path):
    config, root = _config(tmp_path)
    a, b = root / "a.md", root / "b.md"
    a.write_text("# One\n\nFirst.", encoding="utf-8")
    b.write_text("# Two\n\nSecond.", encoding="utf-8")
    calls = [0]

    def stop_after_one():
        calls[0] += 1
        return calls[0] >= 2

    paused = run_scan(config, should_pause=stop_after_one)
    assert paused["paused"] is True
    assert paused["processed_ok"] == 1
    assert paused["remaining"] == 1
    assert len(IndexDB(config.db_path).get_all_active_decks()) == 1
    resumed = refresh_archive(config)
    assert resumed["processed_ok"] == 1
    assert resumed["unchanged"] == 1
    assert _data(config)["stats"]["deck_count"] == 2


def test_http_letter_jpeg_preview_and_thumbnail_have_inert_image_mime(tmp_path):
    config, root = _config(tmp_path)
    (root / "view.md").write_text("# Preview\n\nA safe page", encoding="utf-8")
    refresh_archive(config)
    server = create_server(config.output_dir, 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(base + "/data/export.json", timeout=3) as response:
            data = json.load(response)
        assert len(data["slides"]) == 1
        snippet = data["slides"][0]
        for field, expected in (("preview", LETTER_PREVIEW_PIXELS), ("thumb", LETTER_THUMB_PIXELS)):
            with urllib.request.urlopen(base + "/" + snippet[field], timeout=3) as response:
                assert response.status == 200
                assert response.headers["Content-Type"] == "image/jpeg"
                assert response.headers["X-Content-Type-Options"] == "nosniff"
                assert response.read(3) == b"\xff\xd8\xff"
            with Image.open(Path(config.output_dir) / snippet[field]) as image:
                assert image.size == expected
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_settings_can_enable_markdown_without_unpausing(tmp_path):
    cfg, root = _config(tmp_path, types=["pptx", "pdf"])
    config_path = tmp_path / "config.yaml"
    cfg.processing.scan_paused = True
    save_config(cfg, config_path)
    runtime = AgentRuntime(cfg, config_path=config_path)
    returned = runtime.update_settings({
        "scan_roots": [str(root)],
        "file_types": ["pdf", "md"],
        "scan_interval_seconds": 1800,
    })
    assert returned["scan_paused"] is True
    assert returned["file_types"] == ["pdf", "md"]
    saved = load_config(config_path)
    assert saved.processing.scan_paused is True
    assert saved.file_types == ["pdf", "md"]


def test_frontend_keeps_legacy_html_but_new_markdown_uses_letter_image():
    web = Path(__file__).resolve().parents[1] / "web"
    app = (web / "static/js/app.js").read_text(encoding="utf-8")
    index = (web / "templates/index.html.j2").read_text(encoding="utf-8")
    settings = (web / "templates/settings.html.j2").read_text(encoding="utf-8")
    css = (web / "static/css/style.css").read_text(encoding="utf-8")
    js = (web / "static/js/settings.js").read_text(encoding="utf-8")
    assert 'id="modal-markdown"' in index and 'sandbox="allow-same-origin"' in index
    assert 'allow-scripts' not in index and 'allow-top-navigation' not in index
    assert 'data-filetype="md"' in index and 'id="type-md"' in settings
    assert "type-md" in js and "fileTypes.push('md')" in js
    assert 'isLegacyMarkdownHtml' in app and 'markdownFrame.src = slide.preview' in app
    assert 'preview.src = slide.preview || slide.thumb || ""' in app
    assert '"1 of 1 (US Letter)"' in app
    assert '.slide-card.slide-card-letter img' in css
