"""M004b: Windows per-user context, unattended safety and tray boundaries."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from ppt_visual_archive import platform_paths, tray


def test_windows_requires_loaded_user_profile_when_localappdata_missing(tmp_path):
    """Do not write a service-account archive in the System32 profile."""
    with pytest.raises(RuntimeError, match="LOCALAPPDATA"):
        platform_paths.user_data_dir({"HOME": str(tmp_path)}, platform_name="win32")
    with pytest.raises(RuntimeError, match="LOCALAPPDATA"):
        platform_paths.default_config_path({}, platform_name="win32")


def test_windows_user_appdata_path_stays_scoped_and_does_not_require_path_home(tmp_path, monkeypatch):
    """Session 0 has no HOME; user-scoped LOCALAPPDATA takes precedence."""
    def forbidden_home(cls):
        raise RuntimeError("Path.home may not be consulted")

    monkeypatch.setattr(platform_paths.Path, "home", classmethod(forbidden_home))
    app = tmp_path / "Local"
    assert platform_paths.user_data_dir({"LOCALAPPDATA": str(app)}, platform_name="win32") == (
        app / platform_paths.APP_DIR_NAME
    )


def test_mac_and_xdg_explicit_environment_paths_do_not_probe_home(tmp_path, monkeypatch):
    def forbidden_home(cls):
        raise RuntimeError("Path.home may not be consulted")

    monkeypatch.setattr(platform_paths.Path, "home", classmethod(forbidden_home))
    assert platform_paths.user_data_dir({"HOME": str(tmp_path)}, platform_name="darwin") == (
        tmp_path / "Library" / "Application Support" / platform_paths.APP_DIR_NAME
    )
    assert platform_paths.default_log_dir({"HOME": str(tmp_path)}, platform_name="darwin") == (
        tmp_path / "Library" / "Logs" / platform_paths.APP_DIR_NAME
    )
    assert platform_paths.user_data_dir({"XDG_DATA_HOME": str(tmp_path)}, platform_name="linux") == (
        tmp_path / platform_paths.APP_DIR_NAME
    )


def test_non_interactive_tray_is_noop_with_no_win32_gui_import(monkeypatch):
    # No window station or Explorer may be available in a service/test process.
    monkeypatch.setattr(tray, "is_interactive_windows_session", lambda: False)
    assert tray.run_tray(object()) is None


def test_actual_native_session_probe_is_boolean_and_never_opens_gui():
    assert isinstance(tray.is_interactive_windows_session(), bool)
    if os.name != "nt":
        assert tray.is_interactive_windows_session() is False


def test_privacy_safe_mac_source_preflight_handles_utf8_without_locale_dependency():
    # Every build source reader must declare UTF-8 rather than Windows cp1252.
    project = Path(__file__).resolve().parents[1]
    source = (project / "scripts/preflight_macos_package.py").read_text(encoding="utf-8")
    assert ".read_text()" not in source


def test_build_cli_message_is_safe_for_windows_cp1252_console(tmp_path, monkeypatch):
    """PowerShell/Command Prompt legacy code page must not break build success."""
    from click.testing import CliRunner
    from ppt_visual_archive import builder, cli
    from ppt_visual_archive.config import default_config, save_config

    root = tmp_path / "slides"
    root.mkdir()
    config_path = tmp_path / "config.yaml"
    save_config(default_config(str(tmp_path / "viewer"), [str(root)]), config_path)
    published = []
    monkeypatch.setattr(builder, "build_viewer", lambda cfg: published.append(cfg.output_dir))
    response = CliRunner().invoke(cli.main, ["build", "--config", str(config_path)])
    assert response.exit_code == 0, response.output
    assert len(published) == 1
    assert "Viewer built successfully." in response.output
    response.output.encode("cp1252", errors="strict")
    # The console status itself must not disclose a private output path.
    assert str(tmp_path) not in response.output
