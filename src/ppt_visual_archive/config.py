"""Configuration loader."""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from yaml import YAMLError


@dataclass
class RenderConfig:
    thumbnail_width: int = 320
    preview_width: int = 1280
    image_format: str = "jpg"
    jpeg_quality: int = 82
    mac_pptx_backend: str = "powerpoint"  # powerpoint (Mac) or explicit libreoffice
    pptx_conversion_timeout_seconds: int = 300


@dataclass
class ViewerConfig:
    title: str = "PowerPoint Visual Archive"
    group_by_default: str = "day"


@dataclass
class ProcessingConfig:
    incremental: bool = True
    purge_deleted: bool = True
    scan_interval_seconds: int = 1800
    scan_paused: bool = False  # persistent user stop; survives app/login restart


@dataclass
class AppConfig:
    scan_roots: list[str] = field(default_factory=list)
    exclude_dirs: list[str] = field(
        default_factory=lambda: [".git", "__pycache__", "node_modules"]
    )
    exclude_patterns: list[str] = field(default_factory=lambda: ["~$*.pptx"])
    file_types: list[str] = field(default_factory=lambda: ["pptx"])
    output_dir: str = ""
    db_path: str = ""
    render: RenderConfig = field(default_factory=RenderConfig)
    viewer: ViewerConfig = field(default_factory=ViewerConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)

    def resolve_paths(self) -> None:
        """Resolve output_dir and db_path to absolute paths."""
        if self.output_dir:
            self.output_dir = str(Path(self.output_dir).resolve())
        if not self.db_path and self.output_dir:
            self.db_path = str(Path(self.output_dir) / "data" / "index.db")
        if self.db_path:
            self.db_path = str(Path(self.db_path).resolve())


def _merge_section(data: dict[str, Any], cls: type, key: str) -> Any:
    section = data.get(key, {})
    if isinstance(section, dict):
        return cls(**{k: v for k, v in section.items() if k in cls.__dataclass_fields__})
    return cls()


def load_config(path: str | Path) -> AppConfig:
    """Load configuration from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except YAMLError as exc:
        raise ValueError(
            "Invalid YAML configuration. On Windows, prefer forward slashes "
            '(for example "D:/Slides") or single-quoted paths when using backslashes.'
        ) from exc

    cfg = AppConfig(
        scan_roots=data.get("scan_roots", []),
        exclude_dirs=data.get("exclude_dirs", [".git", "__pycache__", "node_modules"]),
        exclude_patterns=data.get("exclude_patterns", ["~$*.pptx"]),
        file_types=data.get("file_types", ["pptx"]),
        output_dir=data.get("output_dir", ""),
        db_path=data.get("db_path", ""),
        render=_merge_section(data, RenderConfig, "render"),
        viewer=_merge_section(data, ViewerConfig, "viewer"),
        processing=_merge_section(data, ProcessingConfig, "processing"),
    )
    cfg.resolve_paths()
    return cfg


def default_config(output_dir: str, scan_roots: list[str] | None = None) -> AppConfig:
    """Create a default configuration with the given output directory."""
    cfg = AppConfig(
        scan_roots=scan_roots or [],
        output_dir=output_dir,
    )
    cfg.resolve_paths()
    return cfg


def save_config(config: AppConfig, path: str | Path, overwrite: bool = False) -> Path:
    """Write an AppConfig using the existing YAML schema."""
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Config file already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "scan_roots": list(config.scan_roots),
        "exclude_dirs": list(config.exclude_dirs),
        "exclude_patterns": list(config.exclude_patterns),
        "file_types": list(config.file_types),
        "output_dir": config.output_dir,
        "db_path": config.db_path,
        "render": {
            "thumbnail_width": config.render.thumbnail_width,
            "preview_width": config.render.preview_width,
            "image_format": config.render.image_format,
            "jpeg_quality": config.render.jpeg_quality,
            "mac_pptx_backend": config.render.mac_pptx_backend,
            "pptx_conversion_timeout_seconds": config.render.pptx_conversion_timeout_seconds,
        },
        "viewer": {
            "title": config.viewer.title,
            "group_by_default": config.viewer.group_by_default,
        },
        "processing": {
            "incremental": config.processing.incremental,
            "purge_deleted": config.processing.purge_deleted,
            "scan_interval_seconds": config.processing.scan_interval_seconds,
            "scan_paused": config.processing.scan_paused,
        },
    }
    # A pause request must survive a crash/restart without leaving truncated
    # YAML. Stage in the same directory and atomically replace the old file.
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}-", dir=target.parent)
    staged = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            if target.exists():
                os.chmod(staged, stat.S_IMODE(target.stat().st_mode))
            yaml.safe_dump(data, stream, sort_keys=False, allow_unicode=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)
    return target
