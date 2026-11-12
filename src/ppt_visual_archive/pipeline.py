"""Processing pipeline — orchestrates scan, render, extract, and index."""

from __future__ import annotations

import os
import shutil
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from .config import AppConfig
from .asset_generations import ImageGeneration
from .extractor import extract_metadata
from .index_db import IndexDB
from .models import ChangeSet, Deck, DeckStatus, ProcessingResult, ScanResult, Slide
from .perf_metrics import TimedRun
from .pdf_processor import extract_and_render_pdf
from .renderer_factory import SlideRenderer, create_pptx_renderer
from .scanner import detect_changes, scan_files
from .utils import ensure_dir, logger, make_deck_id


def run_scan(
    config: AppConfig,
    force: bool = False,
    scan_roots: Iterable[str] | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    """Full scan + process pipeline. Returns summary stats."""
    metrics = TimedRun("scan")
    status = "ok"
    try:
        with metrics.step("total"):
            db = IndexDB(config.db_path)
            try:
                return _run_scan_inner(config, db, force, scan_roots, metrics, progress_callback)
            finally:
                db.close()
    except Exception:
        status = "error"
        raise
    finally:
        metrics.finish(status=status)


def _run_scan_inner(
    config: AppConfig,
    db: IndexDB,
    force: bool,
    scan_roots: Iterable[str] | None,
    metrics: TimedRun,
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    def progress(phase: str, completed: int = 0, total: int | None = None, errors: int = 0) -> None:
        if progress_callback is not None:
            progress_callback({
                "phase": phase, "completed": completed,
                "total": total, "errors": errors,
            })

    # 1. Scan filesystem
    progress("discovering")
    active_roots = [str(Path(root).resolve()) for root in (scan_roots or config.scan_roots)]
    with metrics.step("filesystem_scan"):
        scan_results = scan_files(config, roots=active_roots)
    metrics.count("discovered_files", len(scan_results))
    metrics.count("scan_roots", len(active_roots))

    # 2. Detect changes
    progress("detecting", completed=0, total=len(scan_results))
    with metrics.step("change_detection"):
        if force:
            # Treat everything as new
            changeset = ChangeSet(new=scan_results)
        else:
            changeset = detect_changes(scan_results, db, deletion_scope_roots=active_roots)
    for name in ("new", "changed", "unchanged", "deleted"):
        metrics.count(name, len(getattr(changeset, name)))

    # 3. Handle deletions
    with metrics.step("deletion_updates"):
        for deck_id in changeset.deleted:
            if config.processing.purge_deleted:
                # Keep assets: a previously opened browser can still reference
                # the old JSON generation until its tab reloads. Explicit
                # garbage collection after a retention policy is separate work.
                db.purge_deck(deck_id)
                logger.info("Purged deleted deck from index (assets retained): %s", deck_id)
            else:
                db.mark_deleted(deck_id)
                logger.info("Marked deck as deleted: %s", deck_id)

    # 4. Process new and changed files
    to_process = changeset.new + changeset.changed
    progress("processing", completed=0, total=len(to_process))
    if not to_process:
        metrics.count("processed_slides", 0)
        logger.info("No new or changed files to process")
        return _build_summary(changeset, 0, 0)

    logger.info("Processing %d files...", len(to_process))

    # Keep existing rows intact until successful replacement processing.
    # The new deck and its replacement slide set commit in one transaction.

    # Partition files by type
    pptx_files = [sr for sr in to_process if sr.file_name.lower().endswith(".pptx")]
    pdf_files = [sr for sr in to_process if sr.file_name.lower().endswith(".pdf")]

    success_count = 0
    error_count = 0
    total_to_process = len(to_process)
    processed_index = 0
    processed_slides = 0
    metrics.count("pptx_files_to_process", len(pptx_files))
    metrics.count("pdf_files_to_process", len(pdf_files))

    # ── Process PPTX files with COM renderer ──
    if pptx_files:
        renderer = create_pptx_renderer(config.render)
        try:
            with metrics.step("pptx_renderer_start"):
                renderer.start()
            for sr in pptx_files:
                processed_index += 1
                logger.info(_format_processing_message(processed_index, total_to_process, sr))
                with metrics.step("pptx_render_extract"):
                    result = _process_single_pptx(config, renderer, sr)
                if result.success:
                    with metrics.step("sqlite_upsert"):
                        _commit_with_generation(db, result)
                    success_count += 1
                    processed_slides += len(result.slides)
                    logger.info(
                        "[%d/%d] Processed: %s (%d slides)",
                        processed_index, total_to_process,
                        result.deck.file_name, len(result.slides),
                    )
                else:
                    error_count += 1
                    logger.error(
                        "[%d/%d] Failed: %s — %s",
                        processed_index, total_to_process,
                        sr.file_name, result.error,
                    )
                progress("processing", processed_index, total_to_process, error_count)
        finally:
            with metrics.step("pptx_renderer_stop"):
                renderer.stop()

    # ── Process PDF files ──
    for sr in pdf_files:
        processed_index += 1
        logger.info(_format_processing_message(processed_index, total_to_process, sr))
        with metrics.step("pdf_render_extract"):
            result = _process_single_pdf(config, sr)
        if result.success:
            with metrics.step("sqlite_upsert"):
                _commit_with_generation(db, result)
            success_count += 1
            processed_slides += len(result.slides)
            logger.info(
                "[%d/%d] Processed: %s (%d pages)",
                processed_index, total_to_process,
                result.deck.file_name, len(result.slides),
            )
        else:
            error_count += 1
            logger.error(
                "[%d/%d] Failed: %s — %s",
                processed_index, total_to_process,
                sr.file_name, result.error,
            )
        progress("processing", processed_index, total_to_process, error_count)

    metrics.count("processed_slides", processed_slides)
    metrics.count("processed_ok", success_count)
    metrics.count("processed_err", error_count)
    return _build_summary(changeset, success_count, error_count)


def _commit_with_generation(db: IndexDB, result: ProcessingResult) -> None:
    """Publish index references only after all new images are ready."""
    try:
        db.replace_deck_and_slides(result.deck, result.slides)
    except Exception:
        # SQLite rolls back the prior generation. Remove only this unreferenced
        # new version: the old index/export keep their intact image paths.
        if result.image_generation_dir:
            shutil.rmtree(result.image_generation_dir, ignore_errors=True)
        raise


def _process_single_pptx(
    config: AppConfig, renderer: SlideRenderer, sr: ScanResult
) -> ProcessingResult:
    """Render a PPTX into one new immutable generation, then index original text."""
    deck_id = make_deck_id(sr.file_path)
    deck = Deck(
        deck_id=deck_id, file_path=sr.file_path,
        file_name=sr.file_name, folder_path=sr.folder_path,
        file_size=sr.file_size, modified_time=sr.modified_time,
        processed_time=time.time(), file_signature=sr.file_signature,
        status=DeckStatus.ACTIVE.value,
    )
    with ImageGeneration(config.output_dir, deck_id) as gen:
        try:
            rendered = renderer.export_slides(sr.file_path, str(gen.stage))
        except Exception as exc:
            return ProcessingResult(deck=deck, success=False, error=str(exc))
        try:
            gen.validate(rendered)
        except (RuntimeError, OSError, ValueError) as exc:
            return ProcessingResult(deck=deck, success=False, error=str(exc))

        try:
            metadata = extract_metadata(sr.file_path)
        except Exception as exc:
            logger.warning("Metadata extraction failed for %s: %s", sr.file_name, exc)
            metadata = {"slide_count": len(rendered), "slides": []}
        expected = metadata.get("slide_count", 0)
        if expected and expected != len(rendered):
            return ProcessingResult(
                deck=deck, success=False,
                error=f"Rendered {len(rendered)} slides but source contains {expected}",
            )
        deck.slide_count = len(rendered)
        metadata_slides = {entry["slide_number"]: entry for entry in metadata.get("slides", [])}
        slides: list[Slide] = []
        for record in rendered:
            number = record["slide_number"]
            source = metadata_slides.get(number, {})
            slides.append(Slide(
                slide_id=f"{deck_id}_s{number:03d}", deck_id=deck_id,
                slide_number=number, title=source.get("title", ""),
                subtitle_text=source.get("subtitle_text", ""),
                body_text=source.get("body_text", ""),
                extra_text=source.get("extra_text", ""),
                extracted_text=source.get("extracted_text", ""),
                notes_text=source.get("notes_text", ""),
                thumb_path=gen.relative(record["thumb_path"]),
                preview_path=gen.relative(record["preview_path"]),
                width=record.get("width", 0), height=record.get("height", 0),
            ))
        gen.publish(rendered)
        return ProcessingResult(
            deck=deck, slides=slides, success=True,
            image_generation_dir=str(gen.path),
        )


def _process_single_pdf(config: AppConfig, sr: ScanResult) -> ProcessingResult:
    """Render each PDF page into a fresh immutable image generation."""
    deck_id = make_deck_id(sr.file_path)
    deck = Deck(
        deck_id=deck_id, file_path=sr.file_path,
        file_name=sr.file_name, folder_path=sr.folder_path,
        file_size=sr.file_size, modified_time=sr.modified_time,
        processed_time=time.time(), file_signature=sr.file_signature,
        status=DeckStatus.ACTIVE.value,
    )
    with ImageGeneration(config.output_dir, deck_id) as gen:
        try:
            data = extract_and_render_pdf(sr.file_path, str(gen.stage), config.render)
        except Exception as exc:
            return ProcessingResult(deck=deck, success=False, error=str(exc))
        rendered = data.get("slides") or []
        if data.get("slide_count", 0) <= 0 or len(rendered) != data["slide_count"]:
            return ProcessingResult(
                deck=deck, success=False,
                error="PDF could not be decoded into any readable pages",
            )
        try:
            gen.validate(rendered)
        except (RuntimeError, OSError, ValueError) as exc:
            return ProcessingResult(deck=deck, success=False, error=str(exc))
        deck.slide_count = len(rendered)
        slides: list[Slide] = []
        for page in rendered:
            number = page["slide_number"]
            slides.append(Slide(
                slide_id=f"{deck_id}_s{number:03d}", deck_id=deck_id,
                slide_number=number, title=page.get("title", ""),
                subtitle_text=page.get("subtitle_text", ""),
                body_text=page.get("body_text", ""),
                extra_text=page.get("extra_text", ""),
                extracted_text=page.get("extracted_text", ""),
                notes_text=page.get("notes_text", ""),
                thumb_path=gen.relative(page["thumb_path"]),
                preview_path=gen.relative(page["preview_path"]),
                width=page.get("thumb_width", 0),
                height=page.get("thumb_height", 0),
            ))
        gen.publish(rendered)
        return ProcessingResult(
            deck=deck, slides=slides, success=True,
            image_generation_dir=str(gen.path),
        )


def _format_processing_message(index: int, total: int, sr: ScanResult) -> str:
    return (
        f"[{index}/{total}] Processing: {sr.file_name} | "
        f"directory: {sr.folder_path}"
    )


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
