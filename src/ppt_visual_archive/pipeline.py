"""Processing pipeline — orchestrates scan, render, extract, and index."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from .config import AppConfig
from .extractor import extract_metadata
from .index_db import IndexDB
from .models import ChangeSet, Deck, DeckStatus, ProcessingResult, ScanResult, Slide
from .renderer import PowerPointRenderer
from .scanner import detect_changes, scan_files
from .utils import ensure_dir, logger, make_deck_id


def run_scan(config: AppConfig, force: bool = False) -> dict:
    """Full scan + process pipeline. Returns summary stats."""
    db = IndexDB(config.db_path)
    try:
        return _run_scan_inner(config, db, force)
    finally:
        db.close()


def _run_scan_inner(config: AppConfig, db: IndexDB, force: bool) -> dict:
    # 1. Scan filesystem
    scan_results = scan_files(config)

    # 2. Detect changes
    if force:
        # Treat everything as new
        changeset = ChangeSet(new=scan_results)
    else:
        changeset = detect_changes(scan_results, db)

    # 3. Handle deletions
    for deck_id in changeset.deleted:
        if config.processing.purge_deleted:
            _purge_deck_assets(config, deck_id)
            db.purge_deck(deck_id)
            logger.info("Purged deleted deck: %s", deck_id)
        else:
            db.mark_deleted(deck_id)
            logger.info("Marked deck as deleted: %s", deck_id)

    # 4. Process new and changed files
    to_process = changeset.new + changeset.changed
    if not to_process:
        logger.info("No new or changed files to process")
        return _build_summary(changeset, 0, 0)

    logger.info("Processing %d files...", len(to_process))

    # For changed decks, clean old slides from DB
    for sr in changeset.changed:
        deck_id = make_deck_id(sr.file_path)
        db.delete_slides_for_deck(deck_id)

    success_count = 0
    error_count = 0

    renderer = PowerPointRenderer(config.render)
    try:
        renderer.start()

        for sr in to_process:
            result = _process_single_deck(config, renderer, sr)
            if result.success:
                db.upsert_deck(result.deck)
                db.upsert_slides(result.slides)
                success_count += 1
                logger.info(
                    "Processed: %s (%d slides)", result.deck.file_name, len(result.slides)
                )
            else:
                error_count += 1
                logger.error("Failed: %s — %s", sr.file_name, result.error)
    finally:
        renderer.stop()

    return _build_summary(changeset, success_count, error_count)


def _process_single_deck(
    config: AppConfig, renderer: PowerPointRenderer, sr: ScanResult
) -> ProcessingResult:
    """Process one presentation: render + extract + build deck/slide objects."""
    deck_id = make_deck_id(sr.file_path)
    assets_dir = os.path.join(config.output_dir, "assets", "decks", deck_id)
    ensure_dir(assets_dir)

    deck = Deck(
        deck_id=deck_id,
        file_path=sr.file_path,
        file_name=sr.file_name,
        folder_path=sr.folder_path,
        file_size=sr.file_size,
        modified_time=sr.modified_time,
        processed_time=time.time(),
        file_signature=sr.file_signature,
        status=DeckStatus.ACTIVE.value,
    )

    # ── Render slide images ──
    try:
        render_results = renderer.export_slides(sr.file_path, assets_dir)
    except Exception as e:
        return ProcessingResult(deck=deck, success=False, error=str(e))

    # ── Extract metadata ──
    try:
        meta = extract_metadata(sr.file_path)
    except Exception as e:
        logger.warning("Metadata extraction failed for %s: %s", sr.file_name, e)
        meta = {"slide_count": len(render_results), "slides": []}

    deck.slide_count = max(len(render_results), meta.get("slide_count", 0))

    # ── Build slide objects ──
    slides: list[Slide] = []
    meta_slides = {m["slide_number"]: m for m in meta.get("slides", [])}

    for rr in render_results:
        snum = rr["slide_number"]
        ms = meta_slides.get(snum, {})

        # Relative path from output root for the viewer
        thumb_rel = f"assets/decks/{deck_id}/{rr.get('thumb_path', '')}" if rr.get("thumb_path") else ""
        preview_rel = f"assets/decks/{deck_id}/{rr.get('preview_path', '')}" if rr.get("preview_path") else ""

        slide = Slide(
            slide_id=f"{deck_id}_s{snum:03d}",
            deck_id=deck_id,
            slide_number=snum,
            title=ms.get("title", ""),
            extracted_text=ms.get("extracted_text", ""),
            notes_text=ms.get("notes_text", ""),
            thumb_path=thumb_rel,
            preview_path=preview_rel,
            width=rr.get("width", 0),
            height=rr.get("height", 0),
        )
        slides.append(slide)

    return ProcessingResult(deck=deck, slides=slides, success=True)


def _purge_deck_assets(config: AppConfig, deck_id: str) -> None:
    """Remove the assets directory for a deck."""
    assets_dir = os.path.join(config.output_dir, "assets", "decks", deck_id)
    if os.path.isdir(assets_dir):
        shutil.rmtree(assets_dir, ignore_errors=True)


def _build_summary(changeset: ChangeSet, success: int, errors: int) -> dict:
    return {
        "new": len(changeset.new),
        "changed": len(changeset.changed),
        "unchanged": len(changeset.unchanged),
        "deleted": len(changeset.deleted),
        "processed_ok": success,
        "processed_err": errors,
    }
