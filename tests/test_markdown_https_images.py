"""Public-only HTTPS illustrations in offline Letter previews, plus persistent cache."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image

from ppt_visual_archive import markdown_processor as md
from ppt_visual_archive.agent import AgentRuntime, refresh_archive
from ppt_visual_archive.config import default_config, load_config, save_config
from ppt_visual_archive.remote_image_cache import RemoteImageCache
from ppt_visual_archive.scanner import scan_files


POSTER_URL = "https://images.metahub.space/poster/small/tt5737432/img"


def _red_jpeg() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (500, 300), (245, 25, 16)).save(output, "JPEG")
    return output.getvalue()


def _red_pixels(path: Path) -> int:
    with Image.open(path) as original:
        scaled = original.convert("RGB").resize((110, 142))
        pixels = scaled.load()
        count = 0
        for y in range(142):
            for x in range(110):
                r, g, b = pixels[x, y]
                if r > 160 and r > g * 2 and r > b * 2:
                    count += 1
        return count


def _config(tmp_path):
    root = tmp_path / "notes"
    root.mkdir()
    config = default_config(str(tmp_path / "archive"), [str(root)])
    config.file_types = ["md"]
    return config, root


def _export(config):
    return json.loads((Path(config.output_dir) / "data/export.json").read_text())


def test_https_images_auto_render_and_cached_across_notes_and_runs(tmp_path, monkeypatch):
    config, root = _config(tmp_path)
    assert config.render.markdown_offline_mode is False
    note_a = root / "first.md"
    note_b = root / "second.md"
    note_text = f"## Poster\n\n![Poster for The Nineties]({POSTER_URL})\n"
    note_a.write_text(note_text)
    note_b.write_text(note_text)
    calls = []
    def fake_download(raw):
        calls.append(raw)
        return _red_jpeg()
    monkeypatch.setattr(md, "_fetch_public_https_image", fake_download)
    result = refresh_archive(config)
    assert result["processed_ok"] == 2
    # One download for two separate notes because a sanitized image is cached.
    assert calls == [POSTER_URL]
    for rec in _export(config)["slides"]:
        assert "Poster for The Nineties" in rec["text"]
        for name in ("preview", "thumb"):
            assert _red_pixels(Path(config.output_dir) / rec[name]) > 75
    cache_path = Path(config.output_dir) / "cache/markdown-remote-images"
    assets = list(cache_path.iterdir())
    assert len(assets) == 1 and assets[0].suffix == ".jpg"
    assert len(assets[0].stem) == 64 and "metahub" not in assets[0].name
    assert note_a.read_text() == note_text and note_b.read_text() == note_text
    assert not list(Path(config.output_dir).rglob("local_image_*"))

    # A later independent render fetches no image when the cache already exists.
    monkeypatch.setattr(md, "_fetch_public_https_image", lambda raw: pytest.fail("downloaded twice"))
    out = tmp_path / "fresh"
    rendered = md.render_markdown_snippets(note_a, out,
                                           allowed_roots=[root],
                                           remote_image_cache_dir=cache_path)
    assert _red_pixels(out / rendered[0]["preview_path"]) > 75


def test_offline_mode_disables_remote_images_even_when_cached(tmp_path, monkeypatch):
    config, root = _config(tmp_path)
    note = root / "poster.md"
    note.write_text(f"## Poster\n\n![Poster for The Nineties]({POSTER_URL})\n")
    monkeypatch.setattr(md, "_fetch_public_https_image", lambda raw: _red_jpeg())
    assert refresh_archive(config)["processed_ok"] == 1
    assert _red_pixels(Path(config.output_dir) / _export(config)["slides"][0]["preview"]) > 75
    config.render.markdown_offline_mode = True
    monkeypatch.setattr(md.socket, "getaddrinfo",
                        lambda *args, **kwargs: pytest.fail("offline mode attempted DNS"))
    monkeypatch.setattr(md, "_fetch_public_https_image", lambda raw: pytest.fail("offline mode fetched"))
    result = refresh_archive(config)
    assert result["processed_ok"] == 1 and result["changed"] == 1
    rec = _export(config)["slides"][0]
    assert "Poster for The Nineties" in rec["text"]
    assert _red_pixels(Path(config.output_dir) / rec["preview"]) == 0
    assert refresh_archive(config)["processed_ok"] == 0


def test_public_only_https_policy_rejects_nonpublic_urls_and_dns(monkeypatch):
    monkeypatch.setattr(md.socket, "getaddrinfo",
                        lambda *args, **kwargs: pytest.fail("invalid URL attempted DNS"))
    for url in (
        "http://images.metahub.space/img",
        "https://user:password@images.metahub.space/img",
        "https://images.metahub.space:8080/img",
        "https://127.0.0.1/img", "https://10.0.0.1/secret", "https://[::1]/",
        "https://localhost/secret", "https://printer.local/img",
        "https://printer.home.arpa/img", "https://sub.example.invalid/path",
        "https://foo.internal/img", "file:///etc/passwd",
        "data:image/png;base64,AA==", "//images.metahub.space/path",
        "https://images.metahub.space\\@local.test/", "https://images.metahub.space/x\r\nInjected: yes",
    ):
        assert md._fetch_public_https_image(url) is None, url

    monkeypatch.setattr(md.socket, "getaddrinfo",
                        lambda *args, **kwargs: [
                            (None, None, None, None, ("8.8.8.8", 443)),
                            (None, None, None, None, ("127.0.0.1", 443)),
                        ])
    monkeypatch.setattr(md, "_PinnedPublicHTTPSConnection",
                        lambda *args, **kwargs: pytest.fail("connected with private DNS answer"))
    assert md._fetch_public_https_image(POSTER_URL) is None


def test_https_transport_enforces_redirect_mime_and_size(monkeypatch):
    monkeypatch.setattr(md.socket, "getaddrinfo",
                        lambda *args, **kwargs: [(None, None, None, None, ("8.8.8.8", 443))])
    state = {"status": 200, "mime": "image/jpeg", "length": None, "body": _red_jpeg()}
    captured = []
    class FakeResponse:
        @property
        def status(self): return state["status"]
        def getheader(self, key):
            return state["mime"] if key == "content-type" else (
                state["length"] if key == "content-length" else None
            )
        def read(self, n):
            assert n == md.MAX_LOCAL_IMAGE_BYTES + 1
            return state["body"][:n]
    class FakeConnection:
        def __init__(self, hostname, ip):
            captured.append((hostname, ip))
        def request(self, method, path, headers):
            assert (method, path) == ("GET", "/poster/small/tt5737432/img")
            assert "image/jpeg" in headers["Accept"]
            assert "Cookie" not in headers and "Referer" not in headers
        def getresponse(self): return FakeResponse()
        def close(self): pass
    monkeypatch.setattr(md, "_PinnedPublicHTTPSConnection", FakeConnection)
    assert md._fetch_public_https_image(POSTER_URL) == _red_jpeg()
    assert captured == [("images.metahub.space", "8.8.8.8")]
    for status, mime in ((302, "image/jpeg"), (301, "image/jpeg"), (200, "text/html"),
                         (200, "image/svg+xml"), (404, "image/jpeg")):
        state.update(status=status, mime=mime)
        assert md._fetch_public_https_image(POSTER_URL) is None
    state.update(status=200, mime="image/jpeg", length=str(md.MAX_LOCAL_IMAGE_BYTES + 1))
    assert md._fetch_public_https_image(POSTER_URL) is None
    state.update(length=None, body=b"x" * (md.MAX_LOCAL_IMAGE_BYTES + 1))
    assert md._fetch_public_https_image(POSTER_URL) is None


def test_bad_download_payload_is_inert_and_no_cache_written(tmp_path, monkeypatch):
    config, root = _config(tmp_path)
    (root / "bad.md").write_text(f"## Poster\n\n![broken]({POSTER_URL})\n")
    monkeypatch.setattr(md, "_fetch_public_https_image", lambda raw: b"not a JPEG")
    result = refresh_archive(config)
    assert result["processed_ok"] == 1 and result["processed_err"] == 0
    assert "broken" in _export(config)["slides"][0]["text"]
    assert not list((Path(config.output_dir) / "cache").rglob("*.jpg"))


def test_cache_bounded_eviction_and_unwritable_cache_graceful(tmp_path, monkeypatch):
    from ppt_visual_archive import remote_image_cache as cachemod
    cache = RemoteImageCache(tmp_path / "cache")
    source = tmp_path / "safe.jpg"
    source.write_bytes(_red_jpeg())
    size = source.stat().st_size
    monkeypatch.setattr(cachemod, "MAX_CACHE_BYTES", size + 1)
    url_a = "https://a.site.org/image"
    url_b = "https://b.site.org/image"
    cache.put(url_a, source)
    first_cached = cache.get(url_a)
    assert first_cached is not None
    import os
    os.utime(first_cached, ns=(1, 1))  # deterministic oldest entry
    cache.put(url_b, source)
    assert cache.get(url_a) is None and cache.get(url_b) is not None

    # No cache write means no failed Markdown conversion.
    (tmp_path / "unwritable").mkdir()
    config, root = _config(tmp_path / "unwritable")
    (root / "poster.md").write_text(f"![Poster]({POSTER_URL})")
    monkeypatch.setattr(md, "_fetch_public_https_image", lambda raw: _red_jpeg())
    def blocked_put(self, url, filename):
        raise OSError("disk is read only")
    monkeypatch.setattr(cachemod.RemoteImageCache, "put", blocked_put)
    # The cache must be best-effort, even when the local disk cannot cache.
    assert refresh_archive(config)["processed_ok"] == 1


def test_markdown_only_signature_config_and_settings_roundtrip(tmp_path, monkeypatch):
    config, root = _config(tmp_path)
    (root / "poster.md").write_text(f"![Poster]({POSTER_URL})")
    (root / "other.pdf").write_bytes(b"%PDF-1.4\n")
    config.file_types = ["md", "pdf"]
    before = {entry.file_name: entry.file_signature for entry in scan_files(config)}
    assert before["poster.md"].endswith("|markdown-https-auto-v2")
    config.file_types = ["md"]
    monkeypatch.setattr(md, "_fetch_public_https_image", lambda raw: _red_jpeg())
    assert refresh_archive(config)["processed_ok"] == 1

    settings = tmp_path / "settings.yaml"
    save_config(config, settings)
    runtime = AgentRuntime(config, config_path=settings, refresh_fn=lambda _: {})
    assert runtime.settings_snapshot()["markdown_offline_mode"] is False
    assert runtime.update_settings({"markdown_offline_mode": True})["markdown_offline_mode"]
    assert load_config(settings).render.markdown_offline_mode is True
    for invalid in ("true", 1, 0, None, []):
        with pytest.raises(ValueError, match="markdown_offline_mode"):
            runtime.update_settings({"markdown_offline_mode": invalid})

    config.file_types = ["md", "pdf"]
    after = {entry.file_name: entry.file_signature for entry in scan_files(config)}
    assert after["other.pdf"] == before["other.pdf"]
    assert after["poster.md"].endswith("|markdown-https-offline-v2")
    config.file_types = ["md"]
    changed = refresh_archive(config)
    assert changed["changed"] == 1 and changed["processed_ok"] == 1
    assert refresh_archive(config)["processed_ok"] == 0

    settings.write_text(settings.read_text().replace(
        "markdown_offline_mode: true", "markdown_offline_mode: 'yes'"
    ))
    with pytest.raises(ValueError, match="markdown_offline_mode"):
        load_config(settings)


def test_image_below_first_letter_page_is_not_drawn(tmp_path, monkeypatch):
    config, root = _config(tmp_path)
    note = root / "long.md"
    note.write_text("# Beginning\n\n" + ("lots of text " * 60 + "\n\n") * 36
                    + f"\n## Poster\n\n![Poster]({POSTER_URL})")
    monkeypatch.setattr(md, "_fetch_public_https_image", lambda raw: _red_jpeg())
    records = md.render_markdown_snippets(note, tmp_path / "out",
                                          allowed_roots=[root],
                                          remote_image_cache_dir=tmp_path / "cache")
    assert "Poster" in records[0]["extracted_text"]
    assert _red_pixels(tmp_path / "out" / records[0]["preview_path"]) == 0
