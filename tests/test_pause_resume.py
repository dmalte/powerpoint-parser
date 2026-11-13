"""M008g: pause after current file; save a partial viewer; resume incrementally."""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import fitz
import pytest

from ppt_visual_archive import agent, perf_metrics, pipeline
from ppt_visual_archive.builder import viewer_is_current
from ppt_visual_archive.config import default_config, load_config, save_config
from ppt_visual_archive.index_db import IndexDB
from ppt_visual_archive.server import run_server


def _pdf(path: Path, label: str) -> None:
    doc = fitz.open()
    doc.new_page(width=720, height=405).insert_text((65, 80), label)
    doc.save(path)
    doc.close()


def _port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.load(response)


def _post(url: str) -> tuple[int, dict]:
    req = urllib.request.Request(
        url, data=b"{}", headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=4) as response:
        return response.status, json.load(response)


def _wait(predicate, *, timeout: float = 12):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            result = predicate()
            if result:
                return result
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(.04)
    raise AssertionError("Timed out waiting for expected agent state")


def _start(cfg, config_path: Path, port: int):
    thread = threading.Thread(
        target=agent.run_agent, args=(cfg,),
        kwargs={"config_path": config_path, "port": port,
                "server_fn": run_server},
        daemon=True,
    )
    thread.start()
    return thread


def _shutdown(base: str, thread: threading.Thread) -> None:
    if not thread.is_alive():
        return
    _post(base + "/api/shutdown")
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_pause_publishes_partial_http_archive_and_resume_skips_committed_files(tmp_path, monkeypatch):
    root = tmp_path / "library"
    root.mkdir()
    for n in (1, 2, 3):
        _pdf(root / f"deck-{n}.pdf", f"Private test document {n}")
    cfg = default_config(str(tmp_path / "archive"), [str(root)])
    cfg.file_types = ["pdf"]
    cfg.processing.scan_interval_seconds = 0
    config_path = tmp_path / "config.yaml"
    save_config(cfg, config_path)
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    started = threading.Event()
    release = threading.Event()
    rendered: list[str] = []
    original = pipeline._process_single_pdf

    def slow_first_document(config, record):
        rendered.append(record.file_name)
        if len(rendered) == 1:
            started.set()
            assert release.wait(7), "Pause test blocked in conversion"
        return original(config, record)

    monkeypatch.setattr(pipeline, "_process_single_pdf", slow_first_document)
    port = _port()
    base = f"http://127.0.0.1:{port}"
    thread = _start(cfg, config_path, port)
    try:
        assert started.wait(5), "First PDF conversion never started"
        http, result = _post(base + "/api/pause")
        assert http == 202 and result["paused"] is True
        state = _json(base + "/api/status")
        assert state["scan_paused"] is True
        assert state["status"] == "pausing"
        assert "deck-" not in json.dumps(state["progress"])
        with pytest.raises(urllib.error.HTTPError) as denied:
            _post(base + "/api/scan")
        assert denied.value.code == 409

        release.set()
        paused = _wait(lambda: (
            d if (d := _json(base + "/api/status"))["status"] == "paused" else None
        ), timeout=15)
        assert paused["last_summary"]["processed_ok"] == 1
        assert paused["last_summary"]["remaining"] == 2
        assert paused["last_summary"]["viewer_rebuilt"] is True
        assert paused["progress"]["phase"] == "paused"
        assert len(rendered) == 1
        export = _json(base + "/data/export.json")
        assert export["stats"]["deck_count"] == 1
        assert export["stats"]["slide_count"] == 1
        assert viewer_is_current(cfg)
        with urllib.request.urlopen(base + "/", timeout=3) as response:
            assert 'id="slide-grid"' in response.read().decode("utf-8")
        with urllib.request.urlopen(base + "/" + export["slides"][0]["thumb"], timeout=3) as response:
            assert response.status == 200 and len(response.read()) > 100
        assert load_config(config_path).processing.scan_paused is True
    finally:
        release.set()
        _shutdown(base, thread)

    # Persisted pause survives a new agent process and does not scan on login.
    cfg2 = load_config(config_path)
    thread2 = _start(cfg2, config_path, port)
    try:
        paused_again = _wait(lambda: (
            d if (d := _json(base + "/api/status"))["status"] == "paused" else None
        ))
        assert paused_again["scan_paused"] is True
        assert len(rendered) == 1
        assert _json(base + "/data/export.json")["stats"]["deck_count"] == 1

        http, result = _post(base + "/api/resume")
        assert http == 202 and result["started"] is True
        completed = _wait(lambda: (
            d if (d := _json(base + "/api/status"))["status"] == "idle" else None
        ), timeout=15)
        assert completed["last_summary"]["processed_ok"] == 2
        assert completed["last_summary"]["processed_err"] == 0
        assert not completed["scan_paused"]
        assert _json(base + "/data/export.json")["stats"]["deck_count"] == 3
        assert len(rendered) == 3
        assert load_config(config_path).processing.scan_paused is False
    finally:
        _shutdown(base, thread2)


def test_deletions_deferred_during_paused_scan(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    a, b = root / "a.pdf", root / "b.pdf"
    _pdf(a, "A")
    _pdf(b, "B")
    cfg = default_config(str(tmp_path / "viewer"), [str(root)])
    cfg.file_types = ["pdf"]
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    assert pipeline.run_scan(cfg)["processed_ok"] == 2
    b.unlink()

    # Even if discovery sees the missing document, cancellation cannot purge it.
    paused = pipeline.run_scan(cfg, should_pause=lambda: True)
    assert paused["paused"] is True
    assert paused["deleted"] == 0
    db = IndexDB(cfg.db_path)
    try:
        assert len(db.get_all_active_decks()) == 2
    finally:
        db.close()

    completed = pipeline.run_scan(cfg)
    assert completed["deleted"] == 1
    db = IndexDB(cfg.db_path)
    try:
        assert len(db.get_all_active_decks()) == 1
    finally:
        db.close()


def test_idle_pause_publishes_unpublished_sqlite_and_survives_settings_update(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    _pdf(root / "one.pdf", "Already indexed")
    cfg = default_config(str(tmp_path / "viewer"), [str(root)])
    cfg.file_types = ["pdf"]
    cfg.processing.scan_interval_seconds = 0
    config_path = tmp_path / "config.yaml"
    save_config(cfg, config_path)
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    assert pipeline.run_scan(cfg)["processed_ok"] == 1
    assert not (Path(cfg.output_dir) / "index.html").exists()

    runtime = agent.AgentRuntime(cfg, config_path=config_path)
    pause = runtime.request_pause()
    assert pause["paused"] and pause["publishing"]
    assert runtime._snapshot_thread is not None
    runtime._snapshot_thread.join(timeout=7)
    assert not runtime._snapshot_thread.is_alive()
    assert runtime.status_snapshot()["status"] == "paused"
    assert _json_file(Path(cfg.output_dir) / "data/export.json")["stats"]["deck_count"] == 1
    assert viewer_is_current(cfg)
    assert load_config(config_path).processing.scan_paused is True
    runtime.update_settings({
        "scan_roots": [str(root)],
        "file_types": ["pdf"],
        "scan_interval_seconds": 60,
    })
    assert load_config(config_path).processing.scan_paused is True
    assert runtime.request_refresh() == {"started": False, "reason": "paused"}


def _json_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_pause_racing_with_worker_release_always_publishes_snapshot(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    _pdf(root / "already.pdf", "Committed before pause")
    cfg = default_config(str(tmp_path / "archive"), [str(root)])
    cfg.file_types = ["pdf"]
    config_path = tmp_path / "config.yaml"
    save_config(cfg, config_path)
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")
    assert pipeline.run_scan(cfg)["processed_ok"] == 1
    assert not (Path(cfg.output_dir) / "index.html").exists()

    runtime = agent.AgentRuntime(cfg, config_path=config_path)
    # Simulate an in-flight scan holding the lock just before its completion.
    runtime._refresh_lock.acquire()
    accepted = runtime.request_pause()
    assert accepted["paused"] is True and accepted["publishing"] is True
    assert runtime.status_snapshot()["status"] == "pausing"
    assert runtime.request_resume() == {"started": False, "reason": "busy"}
    runtime._refresh_lock.release()
    runtime._snapshot_thread.join(timeout=8)
    assert not runtime._snapshot_thread.is_alive()
    assert runtime.status_snapshot()["status"] == "paused"
    assert not runtime.status_snapshot()["snapshot_pending"]
    assert viewer_is_current(cfg)
    assert _json_file(Path(cfg.output_dir) / "data/export.json")["stats"]["deck_count"] == 1


def test_pause_state_not_accepted_if_config_persistence_fails(tmp_path, monkeypatch):
    cfg = default_config(str(tmp_path / "archive"), [str(tmp_path)])
    file = tmp_path / "config.yaml"
    save_config(cfg, file)
    runtime = agent.AgentRuntime(cfg, config_path=file)
    original_yaml = file.read_bytes()

    def fail_save(*args, **kwargs):
        raise OSError("simulated read-only file")

    monkeypatch.setattr(agent, "save_config", fail_save)
    with pytest.raises(OSError, match="read-only"):
        runtime.request_pause()
    assert not runtime.scan_paused
    assert cfg.processing.scan_paused is False
    assert file.read_bytes() == original_yaml


def test_pause_resume_controls_shipped_in_both_interfaces():
    root = Path(__file__).resolve().parents[1] / "web"
    settings = (root / "templates/settings.html.j2").read_text()
    viewer = (root / "templates/index.html.j2").read_text()
    settings_js = (root / "static/js/settings.js").read_text()
    agent_js = (root / "static/js/agent-status.js").read_text()
    assert all(tag in settings for tag in ('id="pause-scan"', 'id="resume-scan"'))
    assert all(tag in viewer for tag in ('id="agent-pause"', 'id="agent-resume"'))
    assert all(endpoint in settings_js and endpoint in agent_js for endpoint in ("/api/pause", "/api/resume"))
