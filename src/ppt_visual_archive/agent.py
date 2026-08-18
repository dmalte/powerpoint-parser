"""Long-running per-user desktop agent lifecycle and control state."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import webbrowser
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from .config import AppConfig, save_config
from .platform_paths import default_log_dir
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


class AgentRuntime:
    """Thread-safe state and actions shared by scheduler, HTTP API, and tray."""

    def __init__(
        self,
        config: AppConfig,
        *,
        config_path: str | Path | None = None,
        port: int = 8080,
        refresh_fn: Callable[[AppConfig], dict] | None = None,
    ) -> None:
        self.config = config
        self.config_path = Path(config_path).resolve() if config_path else None
        self.port = port
        self.refresh_fn = refresh_fn or refresh_archive
        self.stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._refresh_lock = threading.Lock()
        self._schedule_condition = threading.Condition()
        self._shutdown_callback: Callable[[], None] | None = None
        self._status = "starting"
        self._last_refresh: str | None = None
        self._last_error: str | None = None
        self._last_summary: dict | None = None
        self.restart_requested = False

    @property
    def scan_interval_seconds(self) -> int:
        return max(0, int(self.config.processing.scan_interval_seconds))

    def bind_shutdown(self, callback: Callable[[], None]) -> None:
        self._shutdown_callback = callback

    def status_snapshot(self) -> dict:
        with self._state_lock:
            return {
                "status": self._status,
                "last_refresh": self._last_refresh,
                "last_error": self._last_error,
                "last_summary": self._last_summary,
                "scan_interval_seconds": self.scan_interval_seconds,
                "scan_roots": list(self.config.scan_roots),
                "file_types": list(self.config.file_types),
                "viewer_url": f"http://127.0.0.1:{self.port}/",
            }

    def settings_snapshot(self) -> dict:
        return {
            "scan_roots": list(self.config.scan_roots),
            "file_types": list(self.config.file_types),
            "scan_interval_seconds": self.scan_interval_seconds,
        }

    def update_settings(self, payload: dict) -> dict:
        if self.config_path is None:
            raise RuntimeError("Settings cannot be persisted because no config path is available")

        roots = payload.get("scan_roots", self.config.scan_roots)
        if not isinstance(roots, list) or not roots:
            raise ValueError("scan_roots must contain at least one folder")
        normalized_roots: list[str] = []
        for raw in roots:
            path = Path(str(raw)).expanduser().resolve()
            if not path.exists() or not path.is_dir():
                raise ValueError(f"Scan root does not exist or is not a folder: {path}")
            normalized_roots.append(str(path))

        file_types = payload.get("file_types", self.config.file_types)
        if not isinstance(file_types, list):
            raise ValueError("file_types must be a list")
        normalized_types = list(dict.fromkeys(str(v).lower().lstrip(".") for v in file_types))
        if not normalized_types or any(v not in {"pptx", "pdf"} for v in normalized_types):
            raise ValueError("file_types must contain pptx, pdf, or both")

        interval = payload.get("scan_interval_seconds", self.scan_interval_seconds)
        if isinstance(interval, bool):
            raise ValueError("scan_interval_seconds must be a non-negative integer")
        try:
            interval = int(interval)
        except (TypeError, ValueError) as exc:
            raise ValueError("scan_interval_seconds must be a non-negative integer") from exc
        if interval < 0:
            raise ValueError("scan_interval_seconds must be a non-negative integer")

        self.config.scan_roots = normalized_roots
        self.config.file_types = normalized_types
        self.config.processing.scan_interval_seconds = interval
        save_config(self.config, self.config_path, overwrite=True)
        with self._schedule_condition:
            self._schedule_condition.notify_all()
        return self.settings_snapshot()

    def perform_refresh(self, *, blocking: bool = True) -> dict:
        acquired = self._refresh_lock.acquire(blocking=blocking)
        if not acquired:
            return {"started": False, "reason": "busy"}
        try:
            with self._state_lock:
                self._status = "scanning"
                self._last_error = None
            try:
                summary = self.refresh_fn(self.config)
            except Exception as exc:
                with self._state_lock:
                    self._status = "error"
                    self._last_error = str(exc)
                raise
            else:
                with self._state_lock:
                    self._status = "idle"
                    self._last_refresh = datetime.now(timezone.utc).isoformat()
                    self._last_summary = summary
                return {"started": True, "summary": summary}
        finally:
            self._refresh_lock.release()

    def request_refresh(self) -> dict:
        if not self._refresh_lock.acquire(blocking=False):
            return {"started": False, "reason": "busy"}

        def worker() -> None:
            try:
                with self._state_lock:
                    self._status = "scanning"
                    self._last_error = None
                try:
                    summary = self.refresh_fn(self.config)
                except Exception as exc:
                    logger.exception("Manual archive refresh failed")
                    with self._state_lock:
                        self._status = "error"
                        self._last_error = str(exc)
                else:
                    with self._state_lock:
                        self._status = "idle"
                        self._last_refresh = datetime.now(timezone.utc).isoformat()
                        self._last_summary = summary
            finally:
                self._refresh_lock.release()

        threading.Thread(target=worker, name="ppt-archive-manual-refresh", daemon=True).start()
        return {"started": True}

    def request_shutdown(self, *, restart: bool = False) -> None:
        self.restart_requested = restart
        self.stop_event.set()
        with self._schedule_condition:
            self._schedule_condition.notify_all()
        if self._shutdown_callback is not None:
            threading.Thread(target=self._shutdown_callback, name="ppt-archive-shutdown", daemon=True).start()

    def open_archive(self) -> None:
        webbrowser.open(f"http://127.0.0.1:{self.port}/")

    def open_settings(self) -> None:
        webbrowser.open(f"http://127.0.0.1:{self.port}/settings.html")

    def open_logs(self) -> None:
        log_dir = default_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(log_dir))
        else:
            raise OSError("Opening the log folder is currently supported on Windows only")


def run_agent(
    config: AppConfig,
    *,
    config_path: str | Path | None = None,
    port: int = 8080,
    scan_interval_seconds: int | None = None,
    stop_event: threading.Event | None = None,
    refresh_fn: Callable[[AppConfig], dict] | None = None,
    server_fn: Callable[..., None] | None = None,
    tray_fn: Callable[[AgentRuntime], None] | None = None,
) -> None:
    """Refresh once, then serve while scheduled refresh and controls run."""
    if scan_interval_seconds is not None:
        config.processing.scan_interval_seconds = scan_interval_seconds

    runtime = AgentRuntime(config, config_path=config_path, port=port, refresh_fn=refresh_fn)
    if stop_event is not None:
        runtime.stop_event = stop_event

    logger.info("Agent startup refresh beginning")
    runtime.perform_refresh()
    logger.info("Agent startup refresh complete")

    scheduler = threading.Thread(
        target=_scheduled_refresh_loop,
        args=(runtime,),
        name="ppt-archive-refresh",
        daemon=True,
    )
    scheduler.start()

    if server_fn is None:
        from .server import run_server

        server_fn = run_server

    if tray_fn is None and os.name == "nt":
        from .tray import run_tray

        tray_fn = run_tray

    if tray_fn is not None:
        threading.Thread(target=tray_fn, args=(runtime,), name="ppt-archive-tray", daemon=True).start()

    try:
        server_fn(config.output_dir, port, control=runtime)
    finally:
        runtime.stop_event.set()
        with runtime._schedule_condition:
            runtime._schedule_condition.notify_all()
        scheduler.join(timeout=2.0)

    if runtime.restart_requested:
        _restart_current_process()


def _scheduled_refresh_loop(runtime: AgentRuntime) -> None:
    while not runtime.stop_event.is_set():
        with runtime._schedule_condition:
            interval = runtime.scan_interval_seconds
            if interval <= 0:
                runtime._schedule_condition.wait(timeout=1.0)
                continue
            notified = runtime._schedule_condition.wait(timeout=interval)
        if runtime.stop_event.is_set():
            break
        if notified:
            continue
        try:
            logger.info("Scheduled archive refresh beginning")
            result = runtime.perform_refresh(blocking=False)
            if not result.get("started"):
                logger.info("Scheduled archive refresh skipped because another refresh is running")
            else:
                logger.info("Scheduled archive refresh complete")
        except Exception:
            logger.exception("Scheduled archive refresh failed; agent will continue serving")


def _restart_current_process() -> None:
    if getattr(sys, "frozen", False):
        command = [sys.executable, *sys.argv[1:]]
    else:
        command = [sys.executable, *sys.argv]
    subprocess.Popen(command)
