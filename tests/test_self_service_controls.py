"""Portable tests for Phase 2 self-service agent controls."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from ppt_visual_archive.agent import AgentRuntime
from ppt_visual_archive.config import default_config, load_config, save_config
from ppt_visual_archive.server import create_server


def test_settings_update_persists_existing_config_schema(tmp_path):
    root_a = tmp_path / "slides-a"
    root_b = tmp_path / "slides-b"
    root_a.mkdir()
    root_b.mkdir()
    config = default_config(str(tmp_path / "archive"), [str(root_a)])
    config_path = tmp_path / "config.yaml"
    save_config(config, config_path)
    runtime = AgentRuntime(config, config_path=config_path, refresh_fn=lambda _cfg: {})

    updated = runtime.update_settings({
        "scan_roots": [str(root_a), str(root_b)],
        "file_types": ["pptx", "pdf"],
        "scan_interval_seconds": 90,
    })

    loaded = load_config(config_path)
    assert updated["scan_interval_seconds"] == 90
    assert loaded.scan_roots == [str(root_a.resolve()), str(root_b.resolve())]
    assert loaded.file_types == ["pptx", "pdf"]
    assert loaded.processing.scan_interval_seconds == 90


def test_settings_reject_missing_scan_root(tmp_path):
    root = tmp_path / "slides"
    root.mkdir()
    config = default_config(str(tmp_path / "archive"), [str(root)])
    config_path = tmp_path / "config.yaml"
    save_config(config, config_path)
    runtime = AgentRuntime(config, config_path=config_path, refresh_fn=lambda _cfg: {})

    with pytest.raises(ValueError, match="does not exist"):
        runtime.update_settings({"scan_roots": [str(tmp_path / "missing")]})


def test_manual_refresh_requests_are_serialized(tmp_path):
    root = tmp_path / "slides"
    root.mkdir()
    started = threading.Event()
    release = threading.Event()

    def slow_refresh(_config):
        started.set()
        release.wait(timeout=2)
        return {"processed_ok": 1}

    runtime = AgentRuntime(default_config(str(tmp_path / "archive"), [str(root)]), refresh_fn=slow_refresh)

    first = runtime.request_refresh()
    assert started.wait(timeout=1)
    second = runtime.request_refresh()
    release.set()

    assert first == {"started": True}
    assert second == {"started": False, "reason": "busy"}

    deadline = time.time() + 2
    while runtime.status_snapshot()["status"] == "scanning" and time.time() < deadline:
        time.sleep(0.01)
    assert runtime.status_snapshot()["status"] == "idle"


def test_http_status_and_settings_endpoints_are_loopback_controls(tmp_path):
    root = tmp_path / "slides"
    root.mkdir()
    output = tmp_path / "archive"
    output.mkdir()
    (output / "index.html").write_text("ok", encoding="utf-8")
    config = default_config(str(output), [str(root)])
    config_path = tmp_path / "config.yaml"
    save_config(config, config_path)
    runtime = AgentRuntime(config, config_path=config_path, refresh_fn=lambda _cfg: {})
    server = create_server(str(output), 0, control=runtime)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    try:
        with urllib.request.urlopen(base + "/api/status", timeout=2) as response:
            status = json.load(response)
        assert status["status"] == "starting"

        body = json.dumps({
            "scan_roots": [str(root)],
            "file_types": ["pdf"],
            "scan_interval_seconds": 15,
        }).encode()
        request = urllib.request.Request(
            base + "/api/settings",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.load(response)
        assert payload["settings"]["file_types"] == ["pdf"]
        assert load_config(config_path).processing.scan_interval_seconds == 15
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_tray_module_imports_without_pywin32_on_non_windows():
    import ppt_visual_archive.tray as tray

    assert callable(tray.run_tray)


def test_settings_assets_are_present():
    project_root = Path(__file__).resolve().parents[1]
    template = (project_root / "web" / "templates" / "settings.html.j2").read_text(encoding="utf-8")
    script = (project_root / "web" / "static" / "js" / "settings.js").read_text(encoding="utf-8")
    assert "/api/settings" in script
    assert "Scan Now" in template
    assert "Restart Agent" in template
    assert 'id="markdown-offline-mode"' in template
    assert "'markdown-offline-mode'" in script
    assert "markdown_offline_mode:" in script
