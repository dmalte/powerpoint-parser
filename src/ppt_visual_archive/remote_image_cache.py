"""Bounded, image-only, archive-local cache for downloaded Markdown illustrations.

Only locally sanitized JPEG/PNG pixels are stored. Cache filenames are URL
SHA-256 digests, never source URL strings; the viewer never needs this cache.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path

MAX_CACHE_BYTES = 256 * 1024 * 1024
MAX_CACHE_ITEMS = 2048
MAX_CACHE_ITEM_BYTES = 12 * 1024 * 1024
_CACHE_NAME = re.compile(r"^[0-9a-f]{64}\.(?:jpg|png)$")


class RemoteImageCache:
    def __init__(self, path: str | Path | None):
        self.root = Path(path) if path is not None else None

    @staticmethod
    def _digest(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def get(self, url: str) -> Path | None:
        if self.root is None:
            return None
        digest = self._digest(url)
        for ext in (".jpg", ".png"):
            candidate = self.root / (digest + ext)
            try:
                if candidate.is_symlink():
                    continue
                size = candidate.stat().st_size
                if 0 < size <= MAX_CACHE_ITEM_BYTES and candidate.is_file():
                    # Cache hits count as recent for bounded LRU eviction.
                    os.utime(candidate, None)
                    return candidate
            except OSError:
                continue
        return None

    def put(self, url: str, sanitized_image: Path) -> None:
        """Best-effort atomic write; cache errors never fail document rendering."""
        if self.root is None:
            return
        if sanitized_image.suffix.lower() not in {".jpg", ".png"}:
            return
        staged = None
        try:
            if not 0 < sanitized_image.stat().st_size <= MAX_CACHE_ITEM_BYTES:
                return
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, temp_path = tempfile.mkstemp(prefix=".image-", dir=self.root)
            staged = Path(temp_path)
            with os.fdopen(fd, "wb") as output, sanitized_image.open("rb") as source:
                shutil.copyfileobj(source, output)
            target = self.root / (self._digest(url) + sanitized_image.suffix.lower())
            os.replace(staged, target)
            staged = None
            self._prune()
        except OSError:
            pass
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    def _prune(self) -> None:
        if self.root is None:
            return
        entries = []
        total = 0
        try:
            for entry in self.root.iterdir():
                if not _CACHE_NAME.fullmatch(entry.name) or entry.is_symlink() or not entry.is_file():
                    continue
                stat = entry.stat()
                total += stat.st_size
                entries.append((stat.st_mtime_ns, entry, stat.st_size))
            if total <= MAX_CACHE_BYTES and len(entries) <= MAX_CACHE_ITEMS:
                return
            remaining = len(entries)
            for _, path, size in sorted(entries):
                if total <= MAX_CACHE_BYTES and remaining <= MAX_CACHE_ITEMS:
                    break
                try:
                    path.unlink()
                except OSError:
                    continue
                total -= size
                remaining -= 1
        except OSError:
            return
