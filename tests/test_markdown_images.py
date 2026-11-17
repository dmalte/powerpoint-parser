"""Safe local images rendered on only the first physical Markdown Letter page."""
from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

import pytest
from PIL import Image

from ppt_visual_archive import perf_metrics
from ppt_visual_archive.agent import refresh_archive
from ppt_visual_archive.config import default_config
from ppt_visual_archive.markdown_processor import (
    LETTER_PREVIEW_PIXELS, LETTER_THUMB_PIXELS, MAX_LOCAL_IMAGE_BYTES,
    render_markdown_snippets,
)
from ppt_visual_archive.server import create_server


@pytest.fixture(autouse=True)
def _metrics(monkeypatch, tmp_path):
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "metrics")


def _config(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    cfg = default_config(str(tmp_path / "archive"), [str(root)])
    cfg.file_types = ["md"]
    return cfg, root


def _image(path, color=(250, 30, 20), mode="RGB"):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, (450, 280), color).save(path)


def _export(config):
    return json.loads((Path(config.output_dir) / "data/export.json").read_text())


def _strong_color_pixels(file: Path, channel: str) -> int:
    """Detect a visible saturated reference image, not Markdown text colors."""
    with Image.open(file) as source:
        pixels = source.convert("RGB").resize((102, 132))
        count = 0
        for y in range(132):
            for x in range(102):
                r, g, b = pixels.getpixel((x, y))
                if channel == "red" and r > 150 and r > g * 2 and r > b * 2:
                    count += 1
                if channel == "green" and g > 120 and g > r * 1.7 and g > b * 1.3:
                    count += 1
                if channel == "blue" and b > 130 and b > r * 2 and b > g * 1.5:
                    count += 1
    return count


def test_relative_encoded_images_render_on_first_letter_page_and_are_not_leaked(tmp_path):
    cfg, root = _config(tmp_path)
    photo = root / "assets" / "my photo.png"
    _image(photo)
    (root / "notes").mkdir()
    note = root / "notes" / "example.md"
    note.write_text(
        "# Embedded image\n\n![First](../assets/my%20photo.png)\n\n"
        "This image is in an allowed sibling directory.\n\n"
        "![Repeat](../assets/my%20photo.png)\n",
        encoding="utf-8",
    )
    before_note, before_photo = note.read_bytes(), photo.read_bytes()
    result = refresh_archive(cfg)
    assert result["processed_ok"] == 1 and result["processed_err"] == 0
    export = _export(cfg)
    assert len(export["slides"]) == export["stats"]["slide_count"] == 1
    rec = export["slides"][0]
    assert "First" in rec["text"] and "Repeat" in rec["text"]
    output = Path(cfg.output_dir)
    for field, size in (("preview", LETTER_PREVIEW_PIXELS), ("thumb", LETTER_THUMB_PIXELS)):
        with Image.open(output / rec[field]) as rendered:
            assert rendered.format == "JPEG" and rendered.size == size
        assert _strong_color_pixels(output / rec[field], "red") > 80
    # The generated one-page JPEG contains visible image pixels. Temporary
    # raster input files do not escape into the immutable archive generation.
    assert sorted(p.name for p in (output / rec["preview"]).parent.iterdir()) == [
        "preview_001.jpg", "thumb_001.jpg"
    ]
    assert note.read_bytes() == before_note and photo.read_bytes() == before_photo


def test_unsafe_symlink_remote_data_svg_and_corrupt_images_remain_inert(tmp_path):
    cfg, root = _config(tmp_path)
    secret = tmp_path / "secret.png"
    _image(secret, color=(0, 0, 0))
    (root / "alias.png").symlink_to(secret)
    (root / "vector.svg").write_text('<svg onload="alert(1)"></svg>')
    (root / "broken.png").write_bytes(b"not an image")
    note = root / "unsafe.md"
    note.write_text(
        "# Images\n\n"
        "![remote](https://example.invalid/leak.png)\n\n"
        "![data](data:image/png;base64,c2VjcmV0)\n\n"
        "![file](file:///etc/passwd)\n\n"
        "![traversal](../secret.png)\n\n"
        "![encoded](%2e%2e/secret.png)\n\n"
        "![symlink](alias.png)\n\n"
        "![svg](vector.svg)\n\n"
        "![bad](broken.png)\n\n"
        "<script>alert(1)</script>\n",
        encoding="utf-8",
    )
    before = note.read_bytes()
    records = render_markdown_snippets(note, tmp_path / "output", allowed_roots=cfg.scan_roots)
    assert len(records) == 1
    assert note.read_bytes() == before
    assert "remote" in records[0]["extracted_text"] and "symlink" in records[0]["extracted_text"]
    assert sorted(p.name for p in (tmp_path / "output").iterdir()) == ["preview_001.jpg", "thumb_001.jpg"]
    with Image.open(tmp_path / "output" / records[0]["preview_path"]) as page:
        page.verify()


def test_large_invalid_image_is_skipped_but_safe_blue_image_renders(tmp_path):
    cfg, root = _config(tmp_path)
    huge = root / "huge.png"
    with huge.open("wb") as stream:
        stream.truncate(MAX_LOCAL_IMAGE_BYTES + 1)
    _image(root / "good.jpg", color=(20, 80, 220))
    note = root / "mixed.md"
    note.write_text("# Safe\n\n![too large](huge.png)\n\n![good](good.jpg)")
    records = render_markdown_snippets(note, tmp_path / "output", allowed_roots=cfg.scan_roots)
    assert "too large" in records[0]["extracted_text"]
    assert _strong_color_pixels(tmp_path / "output" / records[0]["preview_path"], "blue") > 80


def test_changed_markdown_reprocess_keeps_old_letter_generation(tmp_path):
    cfg, root = _config(tmp_path)
    photo = root / "photo.png"
    note = root / "a.md"
    _image(photo, color=(190, 40, 40))
    note.write_text("# First\n\n![diagram](photo.png)")
    assert refresh_archive(cfg)["processed_ok"] == 1
    first = _export(cfg)["slides"][0]
    previous_page = Path(cfg.output_dir) / first["preview"]
    old_page = previous_page.read_bytes()
    note.write_text("# Second\n\n![revised diagram](photo.png)")
    changed = refresh_archive(cfg)
    assert changed["changed"] == 1 and changed["processed_ok"] == 1
    slides = _export(cfg)["slides"]
    assert len(slides) == 1
    assert slides[0]["preview"] != first["preview"]
    assert previous_page.read_bytes() == old_page


def test_first_letter_jpeg_served_as_safe_image_without_html(tmp_path):
    cfg, root = _config(tmp_path)
    _image(root / "camera.png")
    (root / "example.md").write_text("# Picture\n\n![camera](camera.png)")
    assert refresh_archive(cfg)["processed_ok"] == 1
    rec = _export(cfg)["slides"][0]
    server = create_server(cfg.output_dir, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for field in ("preview", "thumb"):
            with urllib.request.urlopen(base + "/" + rec[field]) as response:
                assert response.headers["Content-Type"] == "image/jpeg"
                assert response.headers["X-Content-Type-Options"] == "nosniff"
                assert response.read(3) == b"\xff\xd8\xff"
        assert _strong_color_pixels(Path(cfg.output_dir) / rec["preview"], "red") > 80
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_obsidian_vault_relative_image_drawn_without_vault_navigation(tmp_path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    notes = vault / "notes"
    notes.mkdir()
    image = vault / "attachments" / "study graph.png"
    _image(image, color=(40, 170, 70))
    note = notes / "topic.md"
    original = "# Study\n\n![[attachments/study graph.png|400]]\n\n~~~md\n![[other.png]]\n~~~"
    note.write_text(original, encoding="utf-8")
    records = render_markdown_snippets(note, tmp_path / "generated", allowed_roots=[vault])
    assert len(records) == 1
    assert "study graph.png" in records[0]["extracted_text"]
    assert '![[other.png]]' in records[0]["extracted_text"]
    for field in ("preview_path", "thumb_path"):
        assert _strong_color_pixels(tmp_path / "generated" / records[0][field], "green") > 80
    assert note.read_text() == original


def test_image_below_first_letter_page_is_absent_from_both_rasters(tmp_path):
    cfg, root = _config(tmp_path)
    _image(root / "red.png")
    note = root / "notes.md"
    note.write_text(
        "# First page\n\n" + ("ordinary text " * 80 + "\n\n") * 45
        + "## Next content\n\n![red](red.png)\n\nLater paragraph."
    )
    rendered = render_markdown_snippets(note, tmp_path / "out", allowed_roots=cfg.scan_roots)
    assert len(rendered) == 1
    assert "red" in rendered[0]["extracted_text"]
    for field in ("preview_path", "thumb_path"):
        assert _strong_color_pixels(tmp_path / "out" / rendered[0][field], "red") == 0
    assert not list((tmp_path / "out").glob("local_image_*"))
