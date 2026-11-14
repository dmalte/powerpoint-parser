"""Filesystem scanner for .pptx files."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterable

from .config import AppConfig
from .index_db import IndexDB
from .models import ChangeSet, ScanResult
from .utils import logger


class ScanInventory(list[ScanResult]):
    """Found files plus whether a transiently vanished entry made discovery incomplete."""

    def __init__(self) -> None:
        super().__init__()
        self.skipped_missing: int = 0


def scan_files(config: AppConfig, roots: Iterable[str] | None = None) -> list[ScanResult]:
    """Recursively scan configured roots for presentation/document files."""
    results = ScanInventory()
    seen_paths: set[str] = set()
    active_roots = [str(Path(root).resolve()) for root in (roots or config.scan_roots)]
    allowed_exts = {ext.lower().lstrip(".") for ext in config.file_types}
    if not active_roots:
        raise ValueError("No scan roots configured; refusing to infer deletions")

    # A detached drive must never be treated as an empty library. Check every
    # root before touching the archive; also fail on traversal/stat errors below.
    for root in active_roots:
        path = Path(root)
        if not path.exists():
            raise FileNotFoundError(f"Scan root unavailable: {root}")
        if not path.is_dir():
            raise NotADirectoryError(f"Scan root is not a directory: {root}")

    def on_walk_error(exc: OSError) -> None:
        raise exc

    for root in active_roots:
        root_path = Path(root)
        for dirpath, dirnames, filenames in os.walk(root_path, onerror=on_walk_error):
            # Prune excluded directories (in-place modification of dirnames)
            dirnames[:] = [
                d for d in dirnames
                if d not in config.exclude_dirs
            ]

            for fname in filenames:
                ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                if ext not in allowed_exts:
                    continue

                # Check exclude patterns
                if _matches_any_pattern(fname, config.exclude_patterns):
                    continue

                full_path = os.path.join(dirpath, fname)
                # Normalize path
                full_path = str(Path(full_path).resolve())

                if full_path in seen_paths:
                    continue
                seen_paths.add(full_path)

                try:
                    stat = os.stat(full_path)
                except FileNotFoundError:
                    # A document or symlink target may disappear between
                    # os.walk and stat (e.g., a Syncthing update). Continue
                    # with other files, but flag this scan as incomplete so
                    # the pipeline cannot infer deletions from missing paths.
                    # Other I/O/permission failures still abort the scan.
                    if Path(root).is_dir() and not Path(full_path).exists():
                        results.skipped_missing += 1
                        logger.warning(
                            "One discovered file became unavailable before stat; "
                            "skipping it and deferring deck deletion reconciliation"
                        )
                        continue
                    raise
                except OSError as exc:
                    logger.error("Incomplete scan: cannot stat %s: %s", full_path, exc)
                    raise

                file_size = stat.st_size
                modified_time = stat.st_mtime
                signature = ScanResult.compute_signature(
                    full_path, file_size, modified_time
                )

                results.append(
                    ScanResult(
                        file_path=full_path,
                        file_name=fname,
                        folder_path=str(Path(dirpath).resolve()),
                        file_size=file_size,
                        modified_time=modified_time,
                        file_signature=signature,
                    )
                )

    logger.info(
        "Scanned %d files (%s) across %d roots; %d vanished entries skipped",
        len(results), ", ".join(sorted(allowed_exts)),
        len(active_roots), results.skipped_missing,
    )
    return results


def detect_changes(
    scan_results: list[ScanResult],
    db: IndexDB,
    deletion_scope_roots: Iterable[str] | None = None,
) -> ChangeSet:
    """Compare scan results against the existing index to classify changes."""
    existing = db.get_all_active_signatures()  # {signature: deck_id}
    existing_sigs = set(existing.keys())
    scanned_sigs: set[str] = set()
    scope_roots = None
    if deletion_scope_roots is not None:
        scope_roots = [str(Path(root).resolve()) for root in deletion_scope_roots]

    # Also map file_path -> deck_id for existing decks
    existing_by_path: dict[str, str] = {}
    for deck in db.get_all_active_decks():
        existing_by_path[deck.file_path] = deck.deck_id

    changeset = ChangeSet()

    for sr in scan_results:
        scanned_sigs.add(sr.file_signature)

        if sr.file_signature in existing_sigs:
            # Signature matches — unchanged
            changeset.unchanged.append(sr)
        elif sr.file_path in existing_by_path:
            # Same path but different signature — changed
            changeset.changed.append(sr)
        else:
            # Not seen before — new
            changeset.new.append(sr)

    # Detect deleted: deck_ids whose paths are not in the current scan
    scanned_paths = {sr.file_path for sr in scan_results}
    for path, deck_id in existing_by_path.items():
        if scope_roots and not _path_in_any_root(path, scope_roots):
            continue
        if path not in scanned_paths:
            changeset.deleted.append(deck_id)

    logger.info(
        "Changes: %d new, %d changed, %d unchanged, %d deleted",
        len(changeset.new), len(changeset.changed),
        len(changeset.unchanged), len(changeset.deleted),
    )
    return changeset


def _matches_any_pattern(filename: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(filename, pat):
            return True
    return False


def _path_in_any_root(file_path: str, roots: Iterable[str]) -> bool:
    candidate = Path(file_path).resolve()
    for root in roots:
        try:
            candidate.relative_to(Path(root).resolve())
            return True
        except ValueError:
            continue
    return False
