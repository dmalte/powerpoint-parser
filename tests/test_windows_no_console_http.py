"""Actual Windows GUI executables must serve HTTP without stdout/stderr."""
from __future__ import annotations

import json
import sys
import threading
import urllib.request

from ppt_visual_archive import server as http_module
from ppt_visual_archive import utils


def test_windowless_server_serves_status_html_and_static_files_without_stderr(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<h1>Developer viewer</h1>", encoding="utf-8")
    (tmp_path / "settings.html").write_text("<h1>Developer settings</h1>", encoding="utf-8")

    class FakeControl:
        def status_snapshot(self):
            return {"status": "idle", "scan_paused": False}

    listener = http_module.create_server(str(tmp_path), 0, control=FakeControl())
    worker = threading.Thread(target=listener.serve_forever, daemon=True)
    worker.start()
    address = f"http://127.0.0.1:{listener.server_port}"
    try:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "stderr", None)
            with urllib.request.urlopen(address + "/api/status", timeout=3) as response:
                status = json.load(response)
                assert response.status == 200
            with urllib.request.urlopen(address + "/", timeout=3) as response:
                page = response.read()
            with urllib.request.urlopen(address + "/settings.html", timeout=3) as response:
                settings = response.read()
        assert status["status"] == "idle"
        assert b"Developer viewer" in page
        assert b"Developer settings" in settings
    finally:
        listener.shutdown()
        listener.server_close()
        worker.join(timeout=3)


def test_no_console_logging_does_not_install_stderr_root_handler(monkeypatch):
    import logging

    before = tuple(logging.getLogger().handlers)
    with monkeypatch.context() as patch:
        patch.setattr(utils.sys, "stderr", None)
        utils.setup_logging()
    after = tuple(logging.getLogger().handlers)
    assert after == before


def test_viewer_request_log_method_does_not_leak_private_paths():
    # The logging callback itself must be safe with no file descriptor.
    handler = object.__new__(http_module.ViewerRequestHandler)
    assert handler.log_message("GET %s", "PRIVATE_USER_PATH") is None
