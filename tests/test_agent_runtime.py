"""Tests for the per-user installed runtime and desktop-agent lifecycle."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from ppt_visual_archive import builder, cli
from ppt_visual_archive.agent import _scheduled_refresh_loop, run_agent
from ppt_visual_archive.config import AppConfig, default_config, load_config, save_config
from ppt_visual_archive.platform_paths import (
    APP_DIR_NAME,
    default_archive_dir,
    default_config_path,
    user_data_dir,
)


def test_windows_user_data_paths_use_localappdata(tmp_path):
    env = {"LOCALAPPDATA": str(tmp_path / "LocalAppData")}

    root = user_data_dir(env)

    assert root == tmp_path / "LocalAppData" / APP_DIR_NAME
    assert default_config_path(env) == root / "config.yaml"
    assert default_archive_dir(env) == root / "archive"


def test_save_config_round_trip_and_overwrite_protection(tmp_path):
    output = tmp_path / "archive"
    source_root = tmp_path / "slides"
    source_root.mkdir()
    config = default_config(str(output), [str(source_root)])
    config.file_types = ["pptx", "pdf"]
    target = tmp_path / "config.yaml"

    save_config(config, target)
    loaded = load_config(target)

    assert loaded.scan_roots == [str(source_root)]
    assert loaded.output_dir == str(output.resolve())
    assert loaded.file_types == ["pptx", "pdf"]

    try:
        save_config(config, target)
    except FileExistsError:
        pass
    else:
        raise AssertionError("save_config should protect existing files by default")


def test_init_config_creates_default_user_config(monkeypatch, tmp_path):
    scan_root = tmp_path / "slides"
    scan_root.mkdir()
    config_path = tmp_path / "appdata" / "config.yaml"
    archive_dir = tmp_path / "appdata" / "archive"
    monkeypatch.setattr(cli, "default_config_path", lambda: config_path)
    monkeypatch.setattr(cli, "default_archive_dir", lambda: archive_dir)

    result = CliRunner().invoke(
        cli.main,
        ["init-config", "--root", str(scan_root), "--include-pdf"],
    )

    assert result.exit_code == 0, result.output
    loaded = load_config(config_path)
    assert loaded.scan_roots == [str(scan_root.resolve())]
    assert loaded.output_dir == str(archive_dir.resolve())
    assert loaded.file_types == ["pptx", "pdf"]


def test_config_candidates_preserve_development_precedence(monkeypatch, tmp_path):
    installed = tmp_path / "installed.yaml"
    monkeypatch.setattr(cli, "default_config_path", lambda: installed)

    candidates = cli._config_candidates()

    assert candidates == [Path("config.yaml"), Path("config") / "config.yaml", installed]


def test_agent_refreshes_before_starting_server(tmp_path):
    config = AppConfig(output_dir=str(tmp_path / "archive"))
    calls: list[str] = []

    def refresh_fn(_config):
        calls.append("refresh")
        return {}

    def server_fn(_output_dir, _port):
        calls.append("serve")

    run_agent(
        config,
        scan_interval_seconds=0,
        refresh_fn=refresh_fn,
        server_fn=server_fn,
    )

    assert calls == ["refresh", "serve"]


def test_scheduled_refresh_failure_is_isolated(tmp_path):
    config = AppConfig(output_dir=str(tmp_path / "archive"))

    class StopAfterSecondWait:
        def __init__(self):
            self.calls = 0

        def wait(self, _seconds):
            self.calls += 1
            return self.calls > 1

    refresh_calls = 0

    def failing_refresh(_config):
        nonlocal refresh_calls
        refresh_calls += 1
        raise RuntimeError("boom")

    _scheduled_refresh_loop(config, 1, StopAfterSecondWait(), failing_refresh)

    assert refresh_calls == 1


def test_web_dir_uses_pyinstaller_bundle_root(monkeypatch, tmp_path):
    monkeypatch.setattr(builder.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert builder._web_dir() == tmp_path / "web"
