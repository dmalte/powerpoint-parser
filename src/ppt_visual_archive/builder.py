"""Static HTML viewer builder."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime
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


# The marker is written last. A source change or failed publication makes the next
# incremental refresh rebuild even if the scanner found no document changes.
VIEWER_BUILD_VERSION = 1
_BUILD_MARKER = ".viewer-build.json"
_PUBLISHED_CORE = (Path("settings.html"), Path("data/export.json"), Path("index.html"))


def _static_sources(web_dir: Path) -> list[Path]:
    """CSS/JS files shipped with the generated viewer, in stable path order."""
    return sorted(
        path.relative_to(web_dir / "static")
        for subdir in ("css", "js")
        for path in (web_dir / "static" / subdir).rglob("*")
        if path.is_file()
    )


def _source_fingerprint(config: AppConfig, web_dir: Path) -> str:
    """Digest generator assets and relevant viewer settings without storing paths."""
    checksum = hashlib.sha256()
    checksum.update(f"viewer-format:{VIEWER_BUILD_VERSION}\n".encode("ascii"))
    checksum.update(json.dumps(
        {"title": config.viewer.title, "group": config.viewer.group_by_default},
        sort_keys=True, ensure_ascii=False,
    ).encode("utf-8"))
    files = [Path("templates/index.html.j2"), Path("templates/settings.html.j2")]
    files.extend(Path("static") / rel for rel in _static_sources(web_dir))
    for relative in files:
        checksum.update(relative.as_posix().encode("utf-8"))
        checksum.update(b"\0")
        checksum.update((web_dir / relative).read_bytes())
        checksum.update(b"\0")
    return checksum.hexdigest()


def viewer_is_current(config: AppConfig) -> bool:
    """A prior complete publication is present and matches source assets/config.

    This is a cheap, stat-based freshness check, not a transactional database
    snapshot or a content hashing pass across an entire large export.
    """
    output = Path(config.output_dir)
    try:
        manifest = json.loads((output / _BUILD_MARKER).read_text(encoding="utf-8"))
        if manifest.get("schema_version") != VIEWER_BUILD_VERSION:
            return False
        web_dir = _web_dir()
        if manifest.get("source_fingerprint") != _source_fingerprint(config, web_dir):
            return False
        expected = {relative.as_posix() for relative in _PUBLISHED_CORE}
        expected.update(rel.as_posix() for rel in _static_sources(web_dir))
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != expected:
            return False
        for relative, stamp in files.items():
            stat = (output / relative).stat()
            if not (stat.st_size == stamp["size"] and stat.st_mtime_ns == stamp["mtime_ns"]):
                return False
    except (FileNotFoundError, OSError, ValueError, TypeError, KeyError, AttributeError):
        return False
    return True


def _replace_published_file(staged: Path, destination: Path) -> None:
    """Replace each fully written file atomically, tolerating brief Win32 readers."""
    for attempt in range(6):
        try:
            os.replace(staged, destination)
            return
        except PermissionError:
            if os.name != "nt" or attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def _atomic_write_marker(output: Path, manifest: dict) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=".viewer-marker-", suffix=".tmp", dir=output)
    temp_file = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(manifest, stream, sort_keys=True, separators=(",", ":"))
        _replace_published_file(temp_file, output / _BUILD_MARKER)
    finally:
        temp_file.unlink(missing_ok=True)


def _publish_staged_site(
    output: Path, stage: Path, relative_files: list[Path], source_fingerprint: str
) -> None:
    """Stage first, then publish individual intact files; marker is commit evidence.

    os.replace is atomic per path. A reader loading multiple URLs concurrently can
    still observe different complete generations; immutable snapshots are not
    introduced by this change.
    """
    marker_path = output / _BUILD_MARKER
    # A failed write during publication must force a complete re-build next time.
    marker_path.unlink(missing_ok=True)
    try:
        for relative in relative_files:
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            _replace_published_file(stage / relative, destination)
        stamps = {}
        for relative in relative_files:
            stat = (output / relative).stat()
            stamps[relative.as_posix()] = {
                "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            }
        _atomic_write_marker(output, {
            "schema_version": VIEWER_BUILD_VERSION,
            "source_fingerprint": source_fingerprint,
            "files": stamps,
        })
    except Exception:
        marker_path.unlink(missing_ok=True)
        raise


def _build(config: AppConfig, db: IndexDB, metrics: TimedRun) -> None:
    output = Path(config.output_dir)
    ensure_dir(output)
    web_dir = _web_dir()
    fingerprint = _source_fingerprint(config, web_dir)

    # The live archive is never written during generation. On failure, the
    # previous HTML, JSON and CSS/JS remain available to existing browsers.
    with tempfile.TemporaryDirectory(prefix=".viewer-stage-", dir=output) as stage_name:
        stage = Path(stage_name)
        (stage / "data").mkdir()

        with metrics.step("sqlite_export"):
            data = _export_data(db, config)
        metrics.count("decks", len(data["decks"]))
        metrics.count("slides", len(data["slides"]))

        json_stage = stage / "data" / "export.json"
        with metrics.step("json_write"):
            with json_stage.open("w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
        metrics.count("json_bytes", json_stage.stat().st_size)

        static_files = _static_sources(web_dir)
        with metrics.step("static_assets_copy"):
            for subdir in ("css", "js"):
                src = web_dir / "static" / subdir
                if src.is_dir():
                    shutil.copytree(src, stage / subdir)

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
            (stage / "index.html").write_text(html, encoding="utf-8")

            settings_template = env.get_template("settings.html.j2")
            settings_html = settings_template.render(title=config.viewer.title)
            (stage / "settings.html").write_text(settings_html, encoding="utf-8")

        # Publish static assets and JSON before index.html; the first-run loader
        # must not expose the viewer page until its data and scripts exist.
        publish_order = static_files + list(_PUBLISHED_CORE)
        with metrics.step("publish"):
            _publish_staged_site(output, stage, publish_order, fingerprint)

    logger.info("Published viewer: %s (%d KB JSON)", output / "index.html",
                metrics.counts["json_bytes"] // 1024)


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
