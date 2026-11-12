"""Tests for the per-user installed runtime and desktop-agent lifecycle."""

from __future__ import annotations

from pathlib import Path
from threading import Event

from click.testing import CliRunner

from ppt_visual_archive import builder, cli
from ppt_visual_archive.agent import AgentRuntime, _scheduled_refresh_loop, run_agent
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


def test_agent_starts_server_while_initial_refresh_is_running(tmp_path):
    config = AppConfig(output_dir=str(tmp_path / "archive"))
    refresh_started = Event()
    allow_refresh_finish = Event()
    refresh_finished = Event()
    observed: dict = {}

    def refresh_fn(_config):
        refresh_started.set()
        assert allow_refresh_finish.wait(3), "Viewer did not start while refresh blocked"
        refresh_finished.set()
        return {}

    def server_fn(_output_dir, _port, **kwargs):
        runtime = kwargs["control"]
        assert refresh_started.wait(2)
        observed["output_dir_exists"] = Path(_output_dir).is_dir()
        observed["status_while_serving"] = runtime.status_snapshot()["status"]
        allow_refresh_finish.set()
        assert refresh_finished.wait(2)

    run_agent(
        config,
        scan_interval_seconds=0,
        refresh_fn=refresh_fn,
        server_fn=server_fn,
    )

    assert observed == {"output_dir_exists": True, "status_while_serving": "scanning"}


def test_runtime_records_refresh_failure(tmp_path):
    config = AppConfig(output_dir=str(tmp_path / "archive"))

    def failing_refresh(_config):
        raise RuntimeError("boom")

    runtime = AgentRuntime(config, refresh_fn=failing_refresh)
    try:
        runtime.perform_refresh()
    except RuntimeError:
        pass
    else:
        raise AssertionError("refresh failure should propagate")

    status = runtime.status_snapshot()
    assert status["status"] == "error"
    assert status["last_error"] == "boom"


def test_web_dir_uses_pyinstaller_bundle_root(monkeypatch, tmp_path):
    monkeypatch.setattr(builder.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert builder._web_dir() == tmp_path / "web"
