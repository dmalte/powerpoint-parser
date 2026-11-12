"""Immutable per-deck image generations for PowerPoint and PDF renderers.

A generation is a whole directory, atomically renamed into its final path once
all thumbnail/preview images are complete. The index then points to this unique
version. Previous generations remain until a separate, explicit garbage
collection policy accounts for previously exported HTML and active browsers.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

from .utils import ensure_dir


class ImageGeneration:
    def __init__(self, archive: str | Path, deck_id: str) -> None:
        self.archive = Path(archive)
        self.deck_id = deck_id
        self.root = self.archive / "assets" / "decks" / deck_id
        self.version = "v-" + uuid.uuid4().hex
        self.path = self.root / self.version
        self.stage: Path | None = None
        self.promoted = False

    def __enter__(self) -> "ImageGeneration":
        ensure_dir(self.root)
        self.stage = Path(tempfile.mkdtemp(prefix=".render-", dir=self.root))
        return self

    @staticmethod
    def _safe_file(name: str) -> bool:
        return bool(name) and Path(name).name == name and name not in {".", ".."} and "\\" not in name

    def validate(self, records: list[dict]) -> None:
        if self.stage is None or not records:
            raise RuntimeError("Renderer produced no complete slide images")
        observed: set[int] = set()
        for entry in records:
            number = entry.get("slide_number")
            if not isinstance(number, int) or number < 1 or number in observed:
                raise RuntimeError("Renderer returned invalid or duplicate slide numbers")
            observed.add(number)
            for key in ("thumb_path", "preview_path"):
                name = entry.get(key) or ""
                if not self._safe_file(name):
                    raise RuntimeError("Missing or invalid slide image filename")
                path = self.stage / name
                if not path.is_file() or path.is_symlink() or path.stat().st_size <= 0:
                    raise RuntimeError("Slide image is missing or empty")
        if observed != set(range(1, len(records) + 1)):
            raise RuntimeError("Renderer returned incomplete or out-of-order slide numbers")

    def relative(self, name: str) -> str:
        if not self._safe_file(name):
            raise ValueError("Unsafe slide image name")
        return f"assets/decks/{self.deck_id}/{self.version}/{name}"

    def publish(self, records: list[dict]) -> None:
        self.validate(records)
        assert self.stage is not None
        # Both paths are on the same archive volume, so directory rename
        # publishes the entire set as one complete new generation.
        os.replace(self.stage, self.path)
        self.stage = None
        self.promoted = True

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.stage is not None:
            shutil.rmtree(self.stage, ignore_errors=True)

    def discard_published(self) -> None:
        """Only for a new generation whose SQLite commit failed."""
        if self.promoted:
            shutil.rmtree(self.path, ignore_errors=True)
            self.promoted = False
