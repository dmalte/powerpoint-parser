"""M009: Markdown section snippets, local HTML safety, mixed incremental archive."""
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
    MAX_SOURCE_BYTES, _parser, render_markdown_snippets, split_markdown,
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
    return json.loads((Path(config.output_dir) / "data/export.json").read_text())


def test_markdown_split_respects_frontmatter_nested_headings_and_code_fences():
    tick = chr(96)
    document = (
        "---\ntags: [internal]\n---\n"
        "Intro paragraph.\n\n# Overview\n"
        "Normal text.\n" + tick * 3 + "markdown\n# Not a heading\n" + tick * 3
        + "\n\n## Details\nA paragraph.\n\n"
        + "~~~python\n## Also not a heading\n~~~\n"
        + "\n### Third\nMore text."
    )
    sections = split_markdown(document, "notes")
    assert [x[0] for x in sections] == ["notes", "Overview", "Details", "Third"]
    assert "tags:" not in "".join(fragment for _, fragment in sections)
    assert "# Not a heading" in sections[1][1]
    assert "## Also not a heading" in sections[2][1]


def test_unheaded_long_markdown_gets_bounded_paragraph_snippets():
    document = "\n\n".join(("Paragraph " + str(i) + " " + "readable " * 30) for i in range(30))
    sections = split_markdown(document, "long-note")
    assert len(sections) > 1
    assert sections[0][0] == "long-note"
    assert sections[1][0].startswith("long-note (part 2)")
    assert "".join(text for _, text in sections).replace("\n", "").replace(" ", "") == document.replace("\n", "").replace(" ", "")


def test_markdown_output_renders_tables_code_and_escapes_active_content(tmp_path):
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
    assert source.read_bytes() == before
    assert len(records) == 1
    rec = records[0]
    page = (tmp_path / "generated" / rec["preview_path"]).read_text(encoding="utf-8")
    assert "<table>" in page and "<strong>value</strong>" in page and "<em>emphasis</em>" in page
    assert "<pre>" in page and "safe code" in page
    assert "<script>" not in page and "<img " not in page and "<iframe" not in page
    assert "<a " not in page and "https://bad.example" not in page
    assert "&lt;script&gt;" in page and "Image: remote image" in page
    assert "default-src &#x27;none&#x27;" in page or "default-src 'none'" in page
    assert "lang" in page
    assert "Security &amp; Data" in page
    assert "Rate" in rec["extracted_text"]
    with Image.open(tmp_path / "generated" / rec["thumb_path"]) as image:
        assert image.size == (640, 400) and image.format == "JPEG"


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
    assert deck["stats"]["slide_count"] == 2
    titles = {slide["title"] for slide in deck["slides"]}
    assert titles == {"Heading One", "Heading Two"}
    assert any("Second bold sentence" in slide["body"] for slide in deck["slides"])
    assets = Path(config.output_dir)
    for slide in deck["slides"]:
        assert slide["preview"].endswith(".html")
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
    assert len(slides) == 2
    assert all(slide["preview"] != previous["preview"] for slide in slides)
    assert prior_html.read_bytes() == original_bytes
    assert prior_thumb.is_file()
    assert viewer_is_current(config)


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
        assert db.get_all_slides()[0].title == "Valid"
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


def test_http_html_preview_csp_and_jpeg_asset(tmp_path):
    config, root = _config(tmp_path)
    (root / "view.md").write_text("# Preview\n\nA safe section", encoding="utf-8")
    refresh_archive(config)
    server = create_server(config.output_dir, 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(base + "/data/export.json", timeout=3) as resp:
            data = json.load(resp)
        snippet = data["slides"][0]
        with urllib.request.urlopen(base + "/" + snippet["preview"], timeout=3) as resp:
            page = resp.read().decode()
            assert resp.status == 200
            assert "default-src 'none'" in resp.headers.get("Content-Security-Policy", "")
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            assert "<h1>Preview</h1>" in page
        with urllib.request.urlopen(base + "/" + snippet["thumb"], timeout=3) as resp:
            assert resp.headers.get("Content-Type") == "image/jpeg"
            assert len(resp.read()) > 100
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


def test_frontend_has_html_iframe_filter_and_settings_checkbox():
    web = Path(__file__).resolve().parents[1] / "web"
    app = (web / "static/js/app.js").read_text()
    index = (web / "templates/index.html.j2").read_text()
    settings = (web / "templates/settings.html.j2").read_text()
    js = (web / "static/js/settings.js").read_text()
    assert 'id="modal-markdown"' in index and 'sandbox=""' in index
    assert 'data-filetype="md"' in index
    assert 'id="type-md"' in settings
    assert "type-md" in js and "fileTypes.push('md')" in js
    assert 'markdownFrame.src = slide.preview' in app
    assert 'markdownFrame.hidden = true' in app
