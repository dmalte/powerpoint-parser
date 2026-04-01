"""Simple HTTP server for the viewer output directory."""

from __future__ import annotations

import functools
import http.server
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .utils import logger


def run_server(output_dir: str, port: int = 8080) -> None:
    """Start a local HTTP server serving the output directory."""
    if not os.path.isdir(output_dir):
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

    handler = functools.partial(ViewerRequestHandler, directory=output_dir)
    server = http.server.HTTPServer(("127.0.0.1", port), handler)
    logger.info("Serving %s at http://127.0.0.1:%d", output_dir, port)
    print(f"Serving viewer at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


class ViewerRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route not in {"/api/open-file", "/api/open-folder"}:
            self.send_error(404, "Unknown API endpoint")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
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

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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
