"""Local, path-free timings for archive scans and viewer generation.

Performance telemetry stays in per-user logs; the viewer receives only these
aggregate numeric counters when the user explicitly exports a report.
"""

from __future__ import annotations

import json
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .platform_paths import default_log_dir
from .utils import logger

LOG_NAME = "performance.jsonl"
MAX_LOG_BYTES = 5 * 1024 * 1024


class TimedRun:
    """Aggregate monotonic stage durations and safe numeric counters."""

    def __init__(self, operation: str) -> None:
        if operation not in {"scan", "build"}:
            raise ValueError("Unknown performance operation")
        self.operation = operation
        self.recorded_at = datetime.now(timezone.utc).isoformat()
        self.durations_ms: dict[str, float] = {}
        self.counts: dict[str, int] = {}

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.durations_ms[name] = round(self.durations_ms.get(name, 0.0) + elapsed_ms, 3)

    def count(self, name: str, value: int) -> None:
        self.counts[name] = int(value)

    def finish(self, *, status: str = "ok", log_dir: Path | None = None) -> dict:
        event = {
            "schema_version": 1,
            "recorded_at": self.recorded_at,
            "operation": self.operation,
            "status": "ok" if status == "ok" else "error",
            "durations_ms": dict(self.durations_ms),
            "counts": dict(self.counts),
        }
        target = (log_dir if log_dir is not None else default_log_dir()) / LOG_NAME
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_size >= MAX_LOG_BYTES:
                target.replace(target.with_suffix(".jsonl.1"))
            with target.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, separators=(",", ":")) + "\n")
        except OSError as exc:
            logger.warning("Could not save performance metrics: %s", exc)
        return event


def recent_runs(*, limit: int = 20, log_dir: Path | None = None) -> list[dict]:
    """Read only bounded, schema-shaped events; never return arbitrary log lines."""
    target = (log_dir if log_dir is not None else default_log_dir()) / LOG_NAME
    if not target.is_file():
        return []
    limit = max(1, min(int(limit), 50))
    events: deque[dict] = deque(maxlen=limit)
    try:
        with target.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    data = json.loads(line)
                    if (
                        data.get("schema_version") != 1
                        or data.get("operation") not in {"scan", "build"}
                        or not isinstance(data.get("durations_ms"), dict)
                        or not isinstance(data.get("counts"), dict)
                    ):
                        continue
                    # Project only expected scalar values; ignore any extra fields.
                    events.append({
                        "schema_version": 1,
                        "recorded_at": str(data.get("recorded_at", "")),
                        "operation": data["operation"],
                        "status": "ok" if data.get("status") == "ok" else "error",
                        "durations_ms": {
                            name: value for name, value in data["durations_ms"].items()
                            if isinstance(name, str) and isinstance(value, (int, float)) and not isinstance(value, bool)
                        },
                        "counts": {
                            name: value for name, value in data["counts"].items()
                            if isinstance(name, str) and isinstance(value, int) and not isinstance(value, bool)
                        },
                    })
                except (ValueError, AttributeError, TypeError):
                    continue
    except OSError as exc:
        logger.warning("Could not read performance metrics: %s", exc)
        return []
    return list(events)
