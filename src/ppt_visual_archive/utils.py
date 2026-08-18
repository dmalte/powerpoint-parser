"""Utility helpers."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

logger = logging.getLogger("ppt_visual_archive")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )


def add_file_logging(path: str | Path, verbose: bool = False) -> Path:
    """Attach a durable UTF-8 file handler for installed-agent diagnostics."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    resolved = target.resolve()

    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == resolved:
            return resolved

    handler = logging.FileHandler(resolved, encoding="utf-8")
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(handler)
    return resolved


def make_deck_id(file_path: str) -> str:
    """Generate a deterministic, filesystem-safe deck id.

    Format: <slugified_filename>_<sha256_prefix>
    """
    name = Path(file_path).stem
    slug = _slugify(name)[:60]
    hash_prefix = hashlib.sha256(file_path.encode("utf-8")).hexdigest()[:8]
    return f"{slug}_{hash_prefix}"


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
