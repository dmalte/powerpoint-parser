"""M011 image packaging and isolation tests."""
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
    MAX_LOCAL_IMAGE_BYTES, render_markdown_snippets,
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
    Image.new(mode, (100, 70), color).save(path)


def _export(config):
    return json.loads((Path(config.output_dir) / "data/export.json").read_text())


def test_relative_and_percent_encoded_images_are_copied_offline_and_shown(tmp_path):
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
    before_note = note.read_bytes()
    before_photo = photo.read_bytes()

    result = refresh_archive(cfg)
    assert result["processed_ok"] == 1 and result["processed_err"] == 0
    rec = _export(cfg)["slides"][0]
    output = Path(cfg.output_dir)
    page = (output / rec["preview"]).read_text(encoding="utf-8")
    assert '<img class="md-local-image"' in page
    assert page.count('src="local_image_001.jpg"') == 2
    assert "First" in rec["text"] and "Repeat" in rec["text"]
    assert "img-src &#x27;self&#x27;" in page or "img-src 'self'" in page
    assert "http://" not in page and "https://" not in page
    image_file = (output / rec["preview"]).parent / "local_image_001.jpg"
    assert image_file.is_file()
    assert not ((output / rec["preview"]).parent / "local_image_002.jpg").exists()
    with Image.open(image_file) as safe:
        safe.verify()
    with Image.open(output / rec["thumb"]) as thumbnail:
        colors = thumbnail.convert("RGB")
        # Embedded red image is composited into lower-right thumbnail.
        assert colors.getpixel((560, 320))[0] > colors.getpixel((560, 320))[1] + 80
    assert note.read_bytes() == before_note and photo.read_bytes() == before_photo


def test_outside_root_symlink_remote_data_svg_and_corrupt_images_are_rejected(tmp_path):
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
        "![bad](broken.png)\n",
        encoding="utf-8",
    )
    rendered = render_markdown_snippets(note, tmp_path / "output", allowed_roots=cfg.scan_roots)
    assert len(rendered) == 1
    html = (tmp_path / "output" / rendered[0]["preview_path"]).read_text()
    assert "<img " not in html
    # CommonMark does not tokenize the malformed data: URI as an image;
    # all recognized unsafe references still produce inert placeholders.
    assert html.count('class="md-image-placeholder"') >= 7
    assert "https://example.invalid" not in html
    # Even when CommonMark renders an invalid link as text, it remains inert.
    assert '<a href="file:' not in html and '<img src="file:' not in html
    assert not list((tmp_path / "output").glob("local_image_*"))


def test_large_and_bogus_image_does_not_block_safe_markdown_render(tmp_path):
    cfg, root = _config(tmp_path)
    huge = root / "huge.png"
    with huge.open("wb") as stream:
        stream.truncate(MAX_LOCAL_IMAGE_BYTES + 1)
    _image(root / "good.jpg", color=(20, 80, 220))
    note = root / "mixed.md"
    note.write_text("# Safe\n\n![too large](huge.png)\n\n![good](good.jpg)")
    records = render_markdown_snippets(note, tmp_path / "output", allowed_roots=cfg.scan_roots)
    page = (tmp_path / "output" / records[0]["preview_path"]).read_text()
    assert "Image: too large" in page
    assert 'src="local_image_001.jpg"' in page


def test_encoded_local_images_reprocess_and_old_image_generation_survives(tmp_path):
    cfg, root = _config(tmp_path)
    photo = root / "photo.png"
    note = root / "a.md"
    _image(photo, color=(190, 40, 40))
    note.write_text("# First\n\n![diagram](photo.png)")
    assert refresh_archive(cfg)["processed_ok"] == 1
    first = _export(cfg)["slides"][0]
    previous_page = Path(cfg.output_dir) / first["preview"]
    previous_image = previous_page.parent / "local_image_001.jpg"
    assert previous_image.is_file()
    old_page = previous_page.read_bytes()

    note.write_text("# Second\n\n![revised diagram](photo.png)")
    changed = refresh_archive(cfg)
    assert changed["changed"] == 1 and changed["processed_ok"] == 1
    new = _export(cfg)["slides"][0]
    assert new["preview"] != first["preview"]
    assert previous_page.read_bytes() == old_page
    assert previous_image.is_file()


def test_generated_images_served_with_safe_preview_headers(tmp_path):
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
        with urllib.request.urlopen(base + "/" + rec["preview"]) as response:
            html = response.read().decode()
            csp = response.headers["Content-Security-Policy"]
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert "img-src 'self'" in csp and "script-src 'none'" in csp
            assert "connect-src 'none'" in csp
            assert 'src="local_image_001.jpg"' in html
        path = rec["preview"].rsplit("/", 1)[0] + "/local_image_001.jpg"
        with urllib.request.urlopen(base + "/" + path) as response:
            assert response.headers["Content-Type"].startswith("image/jpeg")
            assert len(response.read()) > 100
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_obsidian_vault_relative_image_embed_renders_without_vault_navigation(tmp_path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    notes = vault / "notes"
    notes.mkdir()
    image = vault / "attachments" / "study graph.png"
    _image(image, color=(40, 170, 100))
    note = notes / "topic.md"
    original = "# Study\n\n![[attachments/study graph.png|400]]\n\n~~~md\n![[other.png]]\n~~~"
    note.write_text(original, encoding="utf-8")
    records = render_markdown_snippets(note, tmp_path / "generated", allowed_roots=[vault])
    page = (tmp_path / "generated" / records[0]["preview_path"]).read_text()
    assert 'src="local_image_001.jpg"' in page
    assert "study graph.png" in page
    assert '![[other.png]]' in page
    assert note.read_text() == original

def test_image_thumbnail_only_uses_image_from_its_own_section(tmp_path):
    cfg, root = _config(tmp_path)
    _image(root / "red.png")
    (root / "notes.md").write_text("# Picture\n\n![red](red.png)\n\n## Text-only\n\nNothing pictorial.")
    rendered = render_markdown_snippets(root / "notes.md", tmp_path / "out", allowed_roots=cfg.scan_roots)
    assert len(rendered) == 2
    with Image.open(tmp_path / "out" / rendered[0]["thumb_path"]) as first:
        first_color = first.convert("RGB").getpixel((560, 320))
    with Image.open(tmp_path / "out" / rendered[1]["thumb_path"]) as second:
        second_color = second.convert("RGB").getpixel((560, 320))
    assert first_color[0] > first_color[1] + 80
    assert abs(second_color[0] - second_color[1]) < 40
