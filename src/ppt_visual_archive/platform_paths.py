"""Per-user application paths for installed and development runtimes."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "PowerPointVisualArchive"


def user_data_dir(
    env: dict[str, str] | None = None, *, platform_name: str | None = None
) -> Path:
    """Return the writable per-user application-data directory."""
    values = os.environ if env is None else env

    local_app_data = values.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DIR_NAME

    platform = sys.platform if platform_name is None else platform_name
    if platform == "win32":
        # A Windows Service / Session 0 shell often has no LOCALAPPDATA.
        # Never silently write a user's archive into the service account's
        # profile or a Unix-style fallback directory.
        raise RuntimeError(
            "LOCALAPPDATA is unavailable; start the archive from the signed-in "
            "Windows user session with a loaded user profile"
        )
    if platform == "darwin":
        home = Path(values["HOME"]) if values.get("HOME") else Path.home()
        return home / "Library" / "Application Support" / APP_DIR_NAME

    xdg_data_home = values.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / APP_DIR_NAME

    home = Path(values["HOME"]) if values.get("HOME") else Path.home()
    return home / ".local" / "share" / APP_DIR_NAME


def default_config_path(
    env: dict[str, str] | None = None, *, platform_name: str | None = None
) -> Path:
    return user_data_dir(env, platform_name=platform_name) / "config.yaml"


def default_archive_dir(
    env: dict[str, str] | None = None, *, platform_name: str | None = None
) -> Path:
    return user_data_dir(env, platform_name=platform_name) / "archive"


def default_log_dir(
    env: dict[str, str] | None = None, *, platform_name: str | None = None
) -> Path:
    platform = sys.platform if platform_name is None else platform_name
    if platform == "darwin":
        values = os.environ if env is None else env
        home = Path(values["HOME"]) if values.get("HOME") else Path.home()
        return home / "Library" / "Logs" / APP_DIR_NAME
    return user_data_dir(env, platform_name=platform_name) / "logs"
