"""Local HTTP server for the viewer and per-user agent controls."""

from __future__ import annotations

import functools
import http.server
import json
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .utils import logger


def create_server(
    output_dir: str, port: int = 8080, *, control: Any | None = None
) -> http.server.ThreadingHTTPServer:
    """Create the loopback-only threaded viewer server without starting it."""
    if not os.path.isdir(output_dir):
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

    handler = functools.partial(ViewerRequestHandler, directory=output_dir, control=control)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    if control is not None and hasattr(control, "bind_shutdown"):
        control.bind_shutdown(server.shutdown)
    return server


def run_server(output_dir: str, port: int = 8080, *, control: Any | None = None) -> None:
    """Start a loopback-only threaded HTTP server serving the output directory."""
    server = create_server(output_dir, port, control=control)
    logger.info("Serving %s at http://127.0.0.1:%d", output_dir, server.server_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by keyboard interrupt")
    finally:
        server.server_close()


class ViewerRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, control: Any | None = None, **kwargs):
        self.control = control
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route in {"/", "/index.html"} and self.control is not None:
            if not (Path(self.directory) / "index.html").is_file():
                self._send_loading_page()
                return
        if route == "/api/performance":
            from .perf_metrics import recent_runs

            self._send_json(200, {"runs": recent_runs(limit=20)})
            return
        if route == "/api/status":
            if not self._require_control():
                return
            self._send_json(200, self.control.status_snapshot())
            return
        if route == "/api/settings":
            if not self._require_control():
                return
            self._send_json(200, self.control.settings_snapshot())
            return
        super().do_GET()

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route in {"/api/open-file", "/api/open-folder"}:
            self._handle_open_action(route)
            return

        if route == "/api/scan":
            if not self._require_control():
                return
            result = self.control.request_refresh()
            self._send_json(202 if result.get("started") else 409, result)
            return

        if route == "/api/settings":
            if not self._require_control():
                return
            try:
                payload = self._read_json()
                settings = self.control.update_settings(payload)
            except Exception as exc:
                logger.warning("Settings update rejected: %s", exc)
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, {"ok": True, "settings": settings})
            return

        if route == "/api/open-logs":
            if not self._require_control():
                return
            try:
                self.control.open_logs()
            except Exception as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, {"ok": True})
            return

        if route == "/api/shutdown":
            if not self._require_control():
                return
            try:
                payload = self._read_json()
            except Exception:
                payload = {}
            restart = bool(payload.get("restart", False))
            self._send_json(202, {"ok": True, "restart": restart})
            self.control.request_shutdown(restart=restart)
            return

        self.send_error(404, "Unknown API endpoint")

    def _send_loading_page(self) -> None:
        """Serve a first-run status view without depending on a built archive."""
        from .builder import _web_dir

        content = (_web_dir() / "static" / "loading.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _handle_open_action(self, route: str) -> None:
        try:
            payload = self._read_json()
            target_path = str(payload.get("path", "")).strip()
            if not target_path:
                raise ValueError("Missing 'path' in request body")

            if route == "/api/open-file":
                _open_file(target_path)
            else:
                _open_folder(target_path)
        except Exception as exc:
            logger.error("Open action failed for %s: %s", route, exc)
            self._send_json(400, {"ok": False, "error": str(exc)})
            return

        self._send_json(200, {"ok": True})

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON request body must be an object")
        return payload

    def _require_control(self) -> bool:
        if self.control is None:
            self._send_json(503, {"ok": False, "error": "Agent controls are unavailable"})
            return False
        return True

    def end_headers(self) -> None:
        route = urlparse(self.path).path
        if route.startswith("/assets/decks/") and Path(route).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            self.send_header("Cache-Control", "private, max-age=0, must-revalidate")
        elif route == "/data/export.json":
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _open_file(target_path: str) -> None:
    path = Path(target_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File does not exist: {path}")
    if os.name != "nt":
        raise OSError("Opening source files is currently supported on Windows only")
    os.startfile(str(path))


def _open_folder(target_path: str) -> None:
    path = Path(target_path)
    if path.is_file():
        folder = path.parent
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", str(path)])
            return
    else:
        folder = path

    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder does not exist: {folder}")
    if os.name != "nt":
        raise OSError("Opening folders is currently supported on Windows only")
    os.startfile(str(folder))
