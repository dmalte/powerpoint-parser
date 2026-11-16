"""M007c: skip clean refreshes and publish intact viewer files to live readers."""

from __future__ import annotations

import json
import shutil
import threading
import time
import urllib.request
from pathlib import Path

import fitz
import pytest

from ppt_visual_archive import builder, perf_metrics
from ppt_visual_archive.agent import refresh_archive
from ppt_visual_archive.config import default_config
from ppt_visual_archive.perf_metrics import recent_runs
from ppt_visual_archive.server import create_server


def _empty_config(tmp_path, monkeypatch):
    root = tmp_path / "presentations"
    root.mkdir()
    config = default_config(str(tmp_path / "viewer"), [str(root)])
    config.file_types = ["pdf"]
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    return config, root


def _read_json(config):
    return json.loads((Path(config.output_dir) / "data/export.json").read_text(encoding="utf-8"))


def test_noop_refresh_does_not_reexport_or_rewrite_site(tmp_path, monkeypatch):
    config, _ = _empty_config(tmp_path, monkeypatch)

    first = refresh_archive(config)
    assert first["viewer_rebuilt"] is True
    assert builder.viewer_is_current(config)
    output = Path(config.output_dir)
    marker = output / ".viewer-build.json"
    marker_data = json.loads(marker.read_text())
    assert marker_data["schema_version"] == builder.VIEWER_BUILD_VERSION
    assert "source_fingerprint" in marker_data
    assert "presentations" not in marker.read_text()
    tracked = [output / "index.html", output / "data/export.json", output / "js/app.js", marker]
    before = [(file.stat().st_size, file.stat().st_mtime_ns) for file in tracked]

    # Even if called again, the expensive renderer/export function must not run.
    monkeypatch.setattr(builder, "build_viewer", lambda _config: pytest.fail("unexpected rebuild"))
    second = refresh_archive(config)
    assert second["viewer_rebuilt"] is False
    assert second["new"] == second["changed"] == second["deleted"] == 0
    assert [(file.stat().st_size, file.stat().st_mtime_ns) for file in tracked] == before
    events = recent_runs(log_dir=tmp_path / "logs")
    assert [event["operation"] for event in events] == ["scan", "build", "scan"]


def test_failed_only_scan_retries_without_rebuilding_current_viewer(tmp_path, monkeypatch):
    config, source = _empty_config(tmp_path, monkeypatch)
    existing = source / "existing.pdf"
    document = fitz.open()
    document.new_page().insert_text((20, 70), "Original indexed slide")
    document.save(existing)
    document.close()

    first = refresh_archive(config)
    assert first["processed_ok"] == 1 and first["viewer_rebuilt"] is True
    assert _read_json(config)["stats"]["slide_count"] == 1
    output = Path(config.output_dir)
    published = [output / "index.html", output / "data/export.json", output / ".viewer-build.json"]
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in published}

    # Neither a damaged indexed source nor a newly discovered invalid source
    # can modify the committed SQLite inventory; both should remain retryable.
    existing.write_bytes(b"invalid changed pdf")
    (source / "new.pdf").write_bytes(b"invalid new pdf")
    with monkeypatch.context() as patch:
        patch.setattr(builder, "build_viewer", lambda _: pytest.fail("failed-only scan rebuilt viewer"))
        for _ in range(2):
            failed = refresh_archive(config)
            assert failed["new"] == 1 and failed["changed"] == 1
            assert failed["processed_ok"] == 0 and failed["processed_err"] == 2
            assert failed["deleted"] == 0 and failed["viewer_rebuilt"] is False
            assert builder.viewer_is_current(config)
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in published} == before

    # Once one previously invalid source recovers, its committed index update
    # must be published even while another source continues to fail.
    repaired = fitz.open()
    repaired.new_page().insert_text((20, 70), "Repaired slide")
    repaired.new_page().insert_text((20, 70), "Another repaired slide")
    repaired.save(existing)
    repaired.close()
    recovered = refresh_archive(config)
    assert recovered["processed_ok"] == 1 and recovered["processed_err"] == 1
    assert recovered["viewer_rebuilt"] is True
    assert _read_json(config)["stats"]["slide_count"] == 2


def test_initial_failed_source_still_publishes_empty_viewer(tmp_path, monkeypatch):
    config, source = _empty_config(tmp_path, monkeypatch)
    (source / "bad.pdf").write_bytes(b"not a valid PDF")

    result = refresh_archive(config)
    assert result["new"] == 1 and result["processed_err"] == 1
    assert result["processed_ok"] == 0 and result["viewer_rebuilt"] is True
    assert builder.viewer_is_current(config)
    assert _read_json(config)["stats"]["slide_count"] == 0


def test_changed_and_deleted_pdf_require_rebuild(tmp_path, monkeypatch):
    config, source = _empty_config(tmp_path, monkeypatch)
    pdf_path = source / "deck.pdf"
    document = fitz.open()
    document.new_page().insert_text((20, 70), "Initial slide")
    document.save(pdf_path)
    document.close()

    created = refresh_archive(config)
    assert created["new"] == created["processed_ok"] == 1
    assert created["viewer_rebuilt"] is True
    assert _read_json(config)["stats"]["slide_count"] == 1
    assert refresh_archive(config)["viewer_rebuilt"] is False

    document = fitz.open()
    document.new_page().insert_text((20, 70), "Changed slide with more text")
    document.new_page().insert_text((20, 70), "Second page")
    document.save(pdf_path, incremental=False, garbage=3, deflate=True)
    document.close()
    changed = refresh_archive(config)
    assert changed["changed"] == changed["processed_ok"] == 1
    assert changed["viewer_rebuilt"] is True
    assert _read_json(config)["stats"]["slide_count"] == 2

    pdf_path.unlink()
    deleted = refresh_archive(config)
    assert deleted["deleted"] == 1
    assert deleted["viewer_rebuilt"] is True
    assert _read_json(config)["stats"]["slide_count"] == 0
    assert refresh_archive(config)["viewer_rebuilt"] is False


def test_missing_or_stale_frontend_forces_refresh_even_without_document_changes(tmp_path, monkeypatch):
    config, _ = _empty_config(tmp_path, monkeypatch)
    assert refresh_archive(config)["viewer_rebuilt"]
    output = Path(config.output_dir)

    (output / "js/app.js").unlink()
    assert builder.viewer_is_current(config) is False
    assert refresh_archive(config)["viewer_rebuilt"] is True
    assert (output / "js/app.js").is_file()

    config.viewer.title = "Updated Viewer Title"
    assert builder.viewer_is_current(config) is False
    assert refresh_archive(config)["viewer_rebuilt"] is True
    assert "Updated Viewer Title" in (output / "index.html").read_text()
    assert refresh_archive(config)["viewer_rebuilt"] is False

    copy = tmp_path / "web-copy"
    shutil.copytree(builder._web_dir(), copy)
    monkeypatch.setattr(builder, "_web_dir", lambda: copy)
    # Fingerprint changes with frontend content, not just on program reinstall.
    assert refresh_archive(config)["viewer_rebuilt"] is False
    style = copy / "static/css/style.css"
    style.write_text(style.read_text(encoding="utf-8") + "\n/* changed stylesheet */\n", encoding="utf-8")
    assert builder.viewer_is_current(config) is False
    assert refresh_archive(config)["viewer_rebuilt"] is True
    assert "changed stylesheet" in (output / "css/style.css").read_text(encoding="utf-8")


def test_failed_stage_preserves_current_site_and_marker(tmp_path, monkeypatch):
    config, _ = _empty_config(tmp_path, monkeypatch)
    refresh_archive(config)
    output = Path(config.output_dir)
    files = ["index.html", "data/export.json", ".viewer-build.json", "js/app.js"]
    previous = {name: (output / name).read_bytes() for name in files}

    def break_export(db, cfg):
        raise RuntimeError("Failed before publishing any files")

    monkeypatch.setattr(builder, "_export_data", break_export)
    with pytest.raises(RuntimeError, match="Failed before publishing"):
        builder.build_viewer(config)
    for name, content in previous.items():
        assert (output / name).read_bytes() == content
    assert builder.viewer_is_current(config)
    assert not list(output.glob(".viewer-stage-*"))


def test_failed_partial_publication_invalidates_marker_and_is_repairable(tmp_path, monkeypatch):
    config, _ = _empty_config(tmp_path, monkeypatch)
    refresh_archive(config)
    output = Path(config.output_dir)
    previous_json = (output / "data/export.json").read_bytes()
    original_replace = builder._replace_published_file

    def interrupt(staged, destination):
        if destination.name == "export.json":
            raise OSError("Simulated publish interruption")
        original_replace(staged, destination)

    with monkeypatch.context() as patch:
        patch.setattr(builder, "_replace_published_file", interrupt)
        with pytest.raises(OSError, match="publish interruption"):
            builder.build_viewer(config)

    assert (output / "data/export.json").read_bytes() == previous_json
    assert not (output / ".viewer-build.json").exists()
    assert not list(output.glob(".viewer-stage-*"))
    assert builder.viewer_is_current(config) is False
    # No changes to indexed documents, but incomplete publication requires a retry.
    summary = refresh_archive(config)
    assert summary["viewer_rebuilt"] is True
    assert builder.viewer_is_current(config)


def test_http_readers_receive_only_complete_old_or_new_json_during_publication(tmp_path, monkeypatch):
    config, _ = _empty_config(tmp_path, monkeypatch)
    refresh_archive(config)
    output = Path(config.output_dir)
    old_bytes = (output / "data/export.json").read_bytes()
    entered_commit = threading.Event()
    allow_commit = threading.Event()
    error: list[BaseException] = []
    original_export = builder._export_data
    original_replace = builder._replace_published_file

    def updated_export(db, cfg):
        data = original_export(db, cfg)
        data["stats"]["deck_count"] = 42
        data["stats"]["slide_count"] = 6000
        data["slides"] = [{"id": f"synthetic-{i}", "body": "x" * 32} for i in range(6000)]
        return data

    def delayed_commit(staged, destination):
        if destination.name == "export.json":
            entered_commit.set()
            assert allow_commit.wait(4), "Test stalled while publishing"
        original_replace(staged, destination)

    server = create_server(str(output), 0)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{server.server_port}/data/export.json"

    def fetch():
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.read()

    def publish():
        try:
            builder.build_viewer(config)
        except BaseException as exc:
            error.append(exc)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(builder, "_export_data", updated_export)
            patch.setattr(builder, "_replace_published_file", delayed_commit)
            thread = threading.Thread(target=publish, daemon=True)
            thread.start()
            assert entered_commit.wait(3)
            for _ in range(15):
                assert fetch() == old_bytes

            allow_commit.set()
            observed = set()
            for _ in range(50):
                data = json.loads(fetch())
                observed.add(data["stats"]["deck_count"])
                assert data["stats"]["deck_count"] in {0, 42}
            thread.join(timeout=4)
            assert not thread.is_alive()
            assert not error, error
            assert 42 in observed or json.loads(fetch())["stats"]["deck_count"] == 42
            assert builder.viewer_is_current(config)
    finally:
        allow_commit.set()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)


def test_first_install_does_not_expose_index_until_json_is_published(tmp_path, monkeypatch):
    from ppt_visual_archive.agent import AgentRuntime

    config, _ = _empty_config(tmp_path, monkeypatch)
    output = Path(config.output_dir)
    output.mkdir()
    runtime = AgentRuntime(config, refresh_fn=lambda _: {})
    server = create_server(str(output), 0, control=runtime)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    original_replace = builder._replace_published_file
    ready_to_publish_index = threading.Event()
    allow_index = threading.Event()
    errors = []

    def delay_index(staged, destination):
        if destination.name == "index.html":
            ready_to_publish_index.set()
            assert allow_index.wait(4)
        original_replace(staged, destination)

    def worker():
        try:
            builder.build_viewer(config)
        except BaseException as exc:
            errors.append(exc)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(builder, "_replace_published_file", delay_index)
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            assert ready_to_publish_index.wait(3)
            # Before index.html is published, all static dependencies are ready,
            # but the entrypoint still returns the loading page.
            with urllib.request.urlopen(url + "/", timeout=2) as response:
                assert b"Preparing your slide archive" in response.read()
            with urllib.request.urlopen(url + "/data/export.json", timeout=2) as response:
                assert json.load(response)["stats"]["deck_count"] == 0
            with urllib.request.urlopen(url + "/js/app.js", timeout=2) as response:
                assert b"PowerPoint Visual Archive" in response.read()

            allow_index.set()
            thread.join(timeout=4)
            assert not thread.is_alive()
            assert not errors, errors
            with urllib.request.urlopen(url + "/", timeout=2) as response:
                html = response.read()
            assert b'id="slide-grid"' in html
            assert builder.viewer_is_current(config)
    finally:
        allow_index.set()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)


def test_export_skips_coarse_last_modified_cache_validation(tmp_path, monkeypatch):
    from email.utils import formatdate

    config, _ = _empty_config(tmp_path, monkeypatch)
    refresh_archive(config)
    server = create_server(config.output_dir, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/data/export.json",
            headers={"If-Modified-Since": formatdate(time.time() + 3600, usegmt=True)},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.status == 200  # Not a stale 304.
            assert response.headers["Cache-Control"] == "no-store"
            assert json.load(response)["stats"]["slide_count"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
