"""Long-running per-user desktop agent lifecycle."""

from __future__ import annotations

import threading
from collections.abc import Callable

from .config import AppConfig
from .utils import logger


def refresh_archive(
    config: AppConfig,
    *,
    scan_fn: Callable[..., dict] | None = None,
    build_fn: Callable[[AppConfig], None] | None = None,
) -> dict:
    """Run one incremental scan followed by a viewer rebuild."""
    if scan_fn is None:
        from .pipeline import run_scan

        scan_fn = run_scan
    if build_fn is None:
        from .builder import build_viewer

        build_fn = build_viewer

    summary = scan_fn(config, force=False)
    build_fn(config)
    return summary


def run_agent(
    config: AppConfig,
    *,
    port: int = 8080,
    scan_interval_seconds: int = 1800,
    stop_event: threading.Event | None = None,
    refresh_fn: Callable[[AppConfig], dict] | None = None,
    server_fn: Callable[[str, int], None] | None = None,
) -> None:
    """Refresh once, then serve while optionally refreshing periodically."""
    if refresh_fn is None:
        refresh_fn = refresh_archive
    if server_fn is None:
        from .server import run_server

        server_fn = run_server

    stop = stop_event or threading.Event()

    logger.info("Agent startup refresh beginning")
    refresh_fn(config)
    logger.info("Agent startup refresh complete")

    scheduler: threading.Thread | None = None
    if scan_interval_seconds > 0:
        scheduler = threading.Thread(
            target=_scheduled_refresh_loop,
            args=(config, scan_interval_seconds, stop, refresh_fn),
            name="ppt-archive-refresh",
            daemon=True,
        )
        scheduler.start()

    try:
        server_fn(config.output_dir, port)
    finally:
        stop.set()
        if scheduler is not None:
            scheduler.join(timeout=2.0)


def _scheduled_refresh_loop(
    config: AppConfig,
    interval_seconds: int,
    stop_event: threading.Event,
    refresh_fn: Callable[[AppConfig], dict],
) -> None:
    while not stop_event.wait(interval_seconds):
        try:
            logger.info("Scheduled archive refresh beginning")
            refresh_fn(config)
            logger.info("Scheduled archive refresh complete")
        except Exception:
            logger.exception("Scheduled archive refresh failed; agent will continue serving")
