"""Simple HTTP server for the viewer output directory."""

from __future__ import annotations

import functools
import http.server
import os

from .utils import logger


def run_server(output_dir: str, port: int = 8080) -> None:
    """Start a local HTTP server serving the output directory."""
    if not os.path.isdir(output_dir):
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=output_dir)
    server = http.server.HTTPServer(("127.0.0.1", port), handler)
    logger.info("Serving %s at http://127.0.0.1:%d", output_dir, port)
    print(f"Serving viewer at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
