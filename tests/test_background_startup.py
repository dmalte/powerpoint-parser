"""Cross-platform startup/progress acceptance checks for the background agent."""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.request

import fitz

from ppt_visual_archive.agent import refresh_archive, run_agent
from ppt_visual_archive.builder import build_viewer
from ppt_visual_archive.config import default_config
from ppt_visual_archive.pipeline import run_scan
from ppt_visual_archive.server import run_server


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get_json(url):
    with urllib.request.urlopen(url, timeout=2) as response:
        return json.load(response)


def _wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except (OSError, TimeoutError):
            pass
        time.sleep(0.05)
    raise AssertionError("Agent did not reach the expected state")


def _stop_agent(base, thread):
    req = urllib.request.Request(
        base + "/api/shutdown", data=b'{"restart":false}',
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=2):
        pass
    thread.join(timeout=4)
    assert not thread.is_alive()


def test_first_run_serves_progress_immediately_then_real_viewer(tmp_path):
    root = tmp_path / "new-library"
    root.mkdir()
    config = default_config(str(tmp_path / "archive"), [str(root)])
    started = threading.Event()
    proceed = threading.Event()
    port = _free_port()

    def slow_build(_config):
        started.set()
        assert proceed.wait(4), "Viewer blocked on initial scan"
        build_viewer(_config)
        return {"new": 0, "changed": 0, "processed_err": 0}

    thread = threading.Thread(
        target=run_agent,
        args=(config,),
        kwargs={"port": port, "scan_interval_seconds": 0, "refresh_fn": slow_build,
                "server_fn": run_server},
        daemon=True,
    )
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        assert started.wait(2)
        status = _wait_for(lambda: _get_json(base + "/api/status"))
        assert status["status"] == "scanning"
        assert status["progress"]["phase"] == "scanning"
        with urllib.request.urlopen(base + "/", timeout=2) as response:
            initial = response.read().decode("utf-8")
            assert response.headers["Cache-Control"] == "no-store"
        assert "Preparing your slide archive" in initial
        assert "location.replace('/')" in initial
        proceed.set()
        assert _wait_for(lambda: _get_json(base + "/api/status")["status"] == "idle")
        with urllib.request.urlopen(base + "/", timeout=2) as response:
            ready = response.read().decode("utf-8")
        assert 'id="slide-grid"' in ready
        assert "Preparing your slide archive" not in ready
    finally:
        proceed.set()
        if thread.is_alive():
            _stop_agent(base, thread)


def test_initial_scan_failure_is_visible_without_stopping_http(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    config = default_config(str(tmp_path / "archive"), [str(root)])
    port = _free_port()

    def broken(_config):
        raise RuntimeError("simulated renderer failure")

    thread = threading.Thread(
        target=run_agent,
        args=(config,),
        kwargs={"port": port, "scan_interval_seconds": 0,
                "refresh_fn": broken, "server_fn": run_server},
        daemon=True,
    )
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        assert _wait_for(lambda: _get_json(base + "/api/status")["status"] == "error")
        status = _get_json(base + "/api/status")
        assert status["progress"]["phase"] == "error"
        assert "simulated renderer failure" in status["last_error"]
        with urllib.request.urlopen(base + "/", timeout=2) as response:
            assert b"Preparing your slide archive" in response.read()
    finally:
        if thread.is_alive():
            _stop_agent(base, thread)


def test_pdf_scan_reports_numeric_phases_without_source_paths(tmp_path, monkeypatch):
    from ppt_visual_archive import perf_metrics

    source = tmp_path / "PRIVATE_SOURCE_FOLDER"
    source.mkdir()
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((70, 70), "Test slide")
    pdf.save(source / "PRIVATE_DECK.pdf")
    pdf.close()

    config = default_config(str(tmp_path / "viewer"), [str(source)])
    config.file_types = ["pdf"]
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    events = []
    summary = run_scan(config, progress_callback=events.append)
    assert summary["processed_ok"] == 1
    phases = [item["phase"] for item in events]
    assert phases[:3] == ["discovering", "detecting", "processing"]
    assert phases[-1] == "processing"
    assert events[-1]["completed"] == 1
    assert events[-1]["total"] == 1
    assert events[-1]["errors"] == 0
    assert "PRIVATE" not in json.dumps(events)
    assert str(tmp_path) not in json.dumps(events)

    rebuild_events = []
    refresh_archive(config, progress_callback=rebuild_events.append)
    assert rebuild_events[-1]["phase"] == "building"
    assert (tmp_path / "viewer" / "index.html").is_file()
