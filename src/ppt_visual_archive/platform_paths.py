"""Per-user application paths for installed and development runtimes."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "PowerPointVisualArchive"


def user_data_dir(env: dict[str, str] | None = None) -> Path:
    """Return the writable per-user application-data directory."""
    values = os.environ if env is None else env

    local_app_data = values.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DIR_NAME

    xdg_data_home = values.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / APP_DIR_NAME

    home = Path(values.get("HOME", str(Path.home())))
    return home / ".local" / "share" / APP_DIR_NAME


def default_config_path(env: dict[str, str] | None = None) -> Path:
    return user_data_dir(env) / "config.yaml"


def default_archive_dir(env: dict[str, str] | None = None) -> Path:
    return user_data_dir(env) / "archive"


def default_log_dir(env: dict[str, str] | None = None) -> Path:
    return user_data_dir(env) / "logs"
