"""Regression coverage for the 6,000-slide viewer performance milestone."""

from __future__ import annotations

import importlib.util
import threading
import urllib.request
from pathlib import Path

from ppt_visual_archive.server import create_server


ROOT = Path(__file__).resolve().parents[1]


def test_grid_render_is_bounded_and_avoids_quadratic_index_lookup():
    source = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "const GRID_PAGE_SIZE = 240;" in source
    assert "slides.indexOf(slide)" not in source
    assert "document.createDocumentFragment()" in source
    assert "searchBlob(s, scopeKey)" in source
    assert "pageSlides = slides.slice" in source


def test_viewer_exposes_pagination_controls():
    template = (ROOT / "web" / "templates" / "index.html.j2").read_text(encoding="utf-8")
    for control in ("page-prev", "page-next", "page-indicator", "result-range"):
        assert f'id="{control}"' in template


def test_benchmark_fixture_builds_exactly_6000_slides():
    script = ROOT / "scripts" / "benchmark_large_archive.py"
    spec = importlib.util.spec_from_file_location("benchmark_large_archive", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    data = module.build_fixture(slide_count=6000, slides_per_deck=30, text_chars=100)
    assert len(data["slides"]) == 6000
    assert len(data["decks"]) == 200


def test_generated_image_assets_get_revalidation_cache_header(tmp_path):
    output = tmp_path / "archive"
    asset = output / "assets" / "decks" / "d1" / "thumb_1.jpg"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"fake-jpeg")
    server = create_server(str(output), 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/assets/decks/d1/thumb_1.jpg", timeout=2
        ) as response:
            assert response.headers["Cache-Control"] == "private, max-age=0, must-revalidate"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
