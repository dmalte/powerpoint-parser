"""Local, privacy-safe conversion retry state (no source paths in storage).

A changed source signature or explicit force/reset always permits a new attempt.
Unchanged encrypted PDFs are held; transient PPTX errors get capped delays.
Malformed/unwritable state fails *open* and never prevents a conversion.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from pathlib import Path

from .config import AppConfig
from .failure_classification import classify_failure
from .models import ScanResult
from .utils import logger

SCHEMA_VERSION = 1
MAX_STATE_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 100_000
BACKOFF_SECONDS = (300, 1800, 7200, 21600)  # 5 min, 30 min, 2 h, 6 h maximum
TRANSIENT_PPTX = frozenset({"powerpoint_automation", "permission_or_access", "timeout"})
CATEGORIES = frozenset({
    "password_or_encrypted", "permission_or_access", "powerpoint_automation",
    "invalid_or_unreadable", "timeout", "unclassified",
})
_HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")



def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def retry_state_path(config: AppConfig) -> Path:
    """A distinct private file *outside* the loopback-served archive root."""
    archive = Path(config.output_dir).expanduser().resolve()
    identity = _hash(str(Path(config.db_path).expanduser().resolve()))[:16]
    return archive.parent / f".pptviewer-retry-{identity}.json"


class RetryState:
    def __init__(self, config: AppConfig):
        self.path = retry_state_path(config)
        self.entries: dict[str, dict] = {}
        self.available = True
        self._load()

    def _load(self) -> None:
        try:
            if not self.path.exists():
                return
            if self.path.stat().st_size > MAX_STATE_BYTES:
                raise ValueError("retry state file exceeds limit")
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("invalid retry schema")
            entries = data.get("entries")
            if not isinstance(entries, dict) or len(entries) > MAX_ENTRIES:
                raise ValueError("invalid retry record count")
            for digest, record in entries.items():
                if not isinstance(digest, str) or not _HEX_SHA256.fullmatch(digest):
                    raise ValueError("invalid retry identity")
                if not isinstance(record, dict):
                    raise ValueError("invalid retry record")
                signature = record.get("signature_digest")
                category = record.get("category")
                failures = record.get("failures")
                due = record.get("retry_after")
                if (not isinstance(signature, str) or not _HEX_SHA256.fullmatch(signature)
                    or category not in CATEGORIES or type(failures) is not int
                    or not 1 <= failures <= 1_000_000 or type(due) not in {int, float}
                    or not math.isfinite(due) or not 0 <= due < 32503680000):
                    raise ValueError("invalid retry fields")
            self.entries = entries
        except (OSError, ValueError, TypeError, UnicodeError):
            # Never suppress attempts based on a corrupt, unknown, or unreadable
            # state file. Preserve the file for diagnosis until an explicit reset.
            self.entries = {}
            self.available = False
            logger.warning("Conversion retry state is unavailable; retry suppression disabled")

    @staticmethod
    def _key(file_path: str) -> str:
        return _hash(str(Path(file_path).expanduser().resolve()))

    def _persist(self) -> bool:
        if not self.available:
            return False
        temp_name = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=".pptviewer-retry-write-", dir=self.path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"schema_version": SCHEMA_VERSION, "entries": self.entries}, stream,
                          separators=(",", ":"), sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self.path)
            return True
        except OSError:
            self.available = False
            logger.warning("Could not persist conversion retry state; suppression disabled")
            return False
        finally:
            if temp_name is not None:
                Path(temp_name).unlink(missing_ok=True)

    def decision(self, item: ScanResult, *, force: bool = False, now: float | None = None) -> str | None:
        """Return `encrypted_hold`, `backoff` or None (eligible)."""
        if not self.available or not self.entries:
            return None
        key = self._key(item.file_path)
        record = self.entries.get(key)
        if not record:
            return None
        if record["signature_digest"] != _hash(item.file_signature):
            # Changed input invalidates its hold, even if previous indexing failed.
            self.entries.pop(key, None)
            self._persist()
            return None
        if force:
            return None
        extension = Path(item.file_path).suffix.lower()
        if extension == ".pdf" and record["category"] == "password_or_encrypted":
            return "encrypted_hold"
        if extension == ".pptx" and record["category"] in TRANSIENT_PPTX:
            current = time.time() if now is None else now
            return "backoff" if current < record["retry_after"] else None
        return None

    def failed(self, item: ScanResult, reason: str, *, now: float | None = None) -> None:
        if not self.available:
            return
        kind = Path(item.file_path).suffix.lower().lstrip(".")
        category = classify_failure(kind, reason)
        tracked = (kind == "pdf" and category == "password_or_encrypted") or (
            kind == "pptx" and category in TRANSIENT_PPTX
        )
        if not tracked:
            self.succeeded(item)
            return
        key = self._key(item.file_path)
        previous = self.entries.get(key)
        failures = (previous["failures"] + 1) if previous and previous["signature_digest"] == _hash(item.file_signature) else 1
        current = time.time() if now is None else now
        due = 0 if kind == "pdf" else current + BACKOFF_SECONDS[min(failures - 1, len(BACKOFF_SECONDS) - 1)]
        self.entries[key] = {
            "signature_digest": _hash(item.file_signature),
            "category": category,
            "failures": failures,
            "retry_after": due,
        }
        self._persist()

    def succeeded(self, item: ScanResult) -> None:
        if self.available and self.entries.pop(self._key(item.file_path), None) is not None:
            self._persist()

    def clear(self, *, file_path: str | None = None, all_entries: bool = False) -> int:
        """Explicit reset. A corrupt state may be replaced *only* on --all."""
        if all_entries == (file_path is not None):
            raise ValueError("Select either all entries or one file")
        if not self.available:
            if not all_entries:
                raise ValueError("Retry state is unavailable; reset all entries to recover")
            self.available = True
            self.entries = {}
            if not self._persist():
                raise OSError("Could not reset retry state")
            return 0
        if all_entries:
            count = len(self.entries)
            if count:
                self.entries.clear()
                if not self._persist():
                    raise OSError("Could not persist retry reset")
            return count
        assert file_path is not None
        key = self._key(file_path)
        if key not in self.entries:
            return 0
        self.entries.pop(key)
        if not self._persist():
            raise OSError("Could not persist retry reset")
        return 1

    def status(self, *, now: float | None = None) -> dict:
        current = time.time() if now is None else now
        held = sum(r["category"] == "password_or_encrypted" for r in self.entries.values())
        waiting = sum(r["category"] in TRANSIENT_PPTX and current < r["retry_after"] for r in self.entries.values())
        due = sum(r["category"] in TRANSIENT_PPTX and current >= r["retry_after"] for r in self.entries.values())
        return {"storage_ok": self.available, "encrypted_held": held if self.available else 0,
                "backoff_waiting": waiting if self.available else 0, "transient_due": due if self.available else 0}
