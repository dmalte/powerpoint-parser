"""Static HTML viewer builder."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .config import AppConfig
from .index_db import IndexDB
from .perf_metrics import TimedRun
from .utils import ensure_dir, logger

# Location of web assets in source installs or a PyInstaller frozen bundle.
def _web_dir() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "web"
    package_dir = Path(__file__).resolve().parent
    return package_dir.parent.parent / "web"


def build_viewer(config: AppConfig) -> None:
    """Generate the static HTML viewer from the current index."""
    metrics = TimedRun("build")
    status = "ok"
    try:
        with metrics.step("total"):
            db = IndexDB(config.db_path)
            try:
                _build(config, db, metrics)
            finally:
                db.close()
    except Exception:
        status = "error"
        raise
    finally:
        metrics.finish(status=status)


def _build(config: AppConfig, db: IndexDB, metrics: TimedRun) -> None:
    output = Path(config.output_dir)
    ensure_dir(output)
    ensure_dir(output / "data")

    # ── Export JSON data ──
    with metrics.step("sqlite_export"):
        data = _export_data(db, config)
    metrics.count("decks", len(data["decks"]))
    metrics.count("slides", len(data["slides"]))
    json_path = output / "data" / "export.json"
    with metrics.step("json_write"):
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    metrics.count("json_bytes", json_path.stat().st_size)
    logger.info("Wrote %s (%d KB)", json_path, json_path.stat().st_size // 1024)

    web_dir = _web_dir()

    # ── Copy static assets ──
    with metrics.step("static_assets_copy"):
        for subdir in ("css", "js"):
            src = web_dir / "static" / subdir
            dst = output / subdir
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)

    # ── Render HTML ──
    with metrics.step("html_render_write"):
        env = Environment(
            loader=FileSystemLoader(str(web_dir / "templates")),
            autoescape=True,
        )
        template = env.get_template("index.html.j2")
        html = template.render(
            title=config.viewer.title,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            stats=data["stats"],
        )
        html_path = output / "index.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("Wrote %s", html_path)

        settings_template = env.get_template("settings.html.j2")
        settings_html = settings_template.render(title=config.viewer.title)
        settings_path = output / "settings.html"
        with open(settings_path, "w", encoding="utf-8") as f:
            f.write(settings_html)
        logger.info("Wrote %s", settings_path)


def _export_data(db: IndexDB, config: AppConfig) -> dict:
    """Build the JSON data structure consumed by the viewer."""
    decks = db.get_all_active_decks()
    all_slides = db.get_all_slides()
    stats = db.get_stats()
    daily = db.get_daily_activity()

    decks_json = []
    for d in decks:
        decks_json.append({
            "id": d.deck_id,
            "file_path": d.file_path,
            "file_name": d.file_name,
            "folder_path": d.folder_path,
            "file_size": d.file_size,
            "modified_time": d.modified_time,
            "modified_date": _ts_to_date(d.modified_time),
            "slide_count": d.slide_count,
        })

    slides_json = []
    for s in all_slides:
        slides_json.append({
            "id": s.slide_id,
            "deck_id": s.deck_id,
            "num": s.slide_number,
            "title": s.title,
            "subtitle": s.subtitle_text,
            "body": s.body_text,
            "extra": s.extra_text,
            "text": s.extracted_text,
            "notes": s.notes_text,
            "thumb": s.thumb_path,
            "preview": s.preview_path,
            "w": s.width,
            "h": s.height,
        })

    # Build folder set
    folders = sorted({d.folder_path for d in decks})

    return {
        "stats": {
            **stats,
            "folder_count": len(folders),
        },
        "decks": decks_json,
        "slides": slides_json,
        "daily": daily,
        "folders": folders,
        "viewer_title": config.viewer.title,
    }


def _ts_to_date(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
