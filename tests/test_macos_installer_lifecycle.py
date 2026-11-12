"""M008b portable installer lifecycle and failure-recovery tests.

Run internal transaction helpers with fake build artifacts, not launchctl or a
real macOS installation. Actual Mac permissions/signing remain unverified.
"""
from __future__ import annotations

import importlib.util
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def installer():
    path = Path(__file__).resolve().parents[1] / "packaging/macos/install_agent.py"
    spec = importlib.util.spec_from_file_location("mac_install_lifecycle", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module



def fake_bundles(root: Path, version: str) -> Path:
    app = root / "PowerPointArchiveAgent.app/Contents/MacOS/PowerPointArchiveAgent"
    app.parent.mkdir(parents=True)
    app.write_text("agent " + version)
    cli = root / "pptviewer/pptviewer"
    cli.parent.mkdir(parents=True)
    cli.write_text("cli " + version)
    return root


def fake_launch(installer, monkeypatch, home: Path, *, fail_bootstrap: int = 0):
    calls = []
    errors = [fail_bootstrap]
    paths = installer.mac_paths(home)

    def run(argv, **kwargs):
        calls.append(argv)
        if "init-config" in argv:
            paths["config"].parent.mkdir(parents=True, exist_ok=True)
            paths["config"].write_text("scan_roots: []\n")
        if "bootstrap" in argv and errors[0]:
            errors[0] -= 1
            raise subprocess.CalledProcessError(1, argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(installer.subprocess, "run", run)
    return calls


def test_clean_install_then_upgraded_app_preserves_user_state(installer, monkeypatch, tmp_path):
    home = tmp_path / "user"
    home.mkdir()
    app_v1 = fake_bundles(tmp_path / "v1", "v1")
    app_v2 = fake_bundles(tmp_path / "v2", "v2")
    folder = tmp_path / "presentations"
    folder.mkdir()
    calls = fake_launch(installer, monkeypatch, home)

    paths = installer.mac_paths(home)
    installer._install_transaction(paths, app_v1, folder, home)
    assert paths["app"].is_dir() and paths["cli"].is_dir()
    assert (paths["app"] / "Contents/MacOS/PowerPointArchiveAgent").read_text() == "agent v1"
    assert paths["config"].read_text() == "scan_roots: []\n"
    (paths["config"].parent / "archive").mkdir()
    (paths["config"].parent / "archive" / "index.db").write_bytes(b"existing db")
    (paths["logs"] / "agent.log").write_text("existing logs")

    # Upgrades work with no --root when the config already exists.
    installer._install_transaction(paths, app_v2, None, home)
    assert (paths["app"] / "Contents/MacOS/PowerPointArchiveAgent").read_text() == "agent v2"
    assert (paths["cli"] / "pptviewer").read_text() == "cli v2"
    assert paths["config"].read_text() == "scan_roots: []\n"
    assert (paths["config"].parent / "archive" / "index.db").read_bytes() == b"existing db"
    assert (paths["logs"] / "agent.log").read_text() == "existing logs"
    assert len([c for c in calls if "init-config" in c]) == 1
    assert not list(home.rglob(".pptviewer-*-stage-*"))
    assert not list(home.rglob(".pptviewer-*-backup-*"))


def test_failed_copy_preserves_old_app_and_launchagent(installer, monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    paths = installer.mac_paths(home)
    calls = fake_launch(installer, monkeypatch, home)
    root = tmp_path / "source"
    root.mkdir()
    installer._install_transaction(paths, fake_bundles(tmp_path / "v1", "old"), root, home)
    old_plist = paths["plist"].read_bytes()
    original_copy = installer.shutil.copytree

    def fail_copy(src, dst, *args, **kwargs):
        if Path(src).name == "pptviewer":
            raise OSError("simulated interrupted copy")
        return original_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(installer.shutil, "copytree", fail_copy)
    with pytest.raises(OSError, match="interrupted copy"):
        installer._install_transaction(paths, fake_bundles(tmp_path / "v2", "new"), None, home)
    assert (paths["app"] / "Contents/MacOS/PowerPointArchiveAgent").read_text() == "agent old"
    assert paths["plist"].read_bytes() == old_plist
    assert not list(home.rglob(".pptviewer-*-stage-*"))


def test_failed_new_agent_bootstrap_rolls_back_app_cli_plist(installer, monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    paths = installer.mac_paths(home)
    source = tmp_path / "presentations"
    source.mkdir()
    calls = fake_launch(installer, monkeypatch, home)
    installer._install_transaction(paths, fake_bundles(tmp_path / "v1", "old"), source, home)
    old_plist = paths["plist"].read_bytes()
    old_app = (paths["app"] / "Contents/MacOS/PowerPointArchiveAgent").read_bytes()
    old_cli = (paths["cli"] / "pptviewer").read_bytes()
    failures = [1]

    def fail_first_bootstrap(argv, **kwargs):
        calls.append(argv)
        if "bootstrap" in argv and failures[0]:
            failures[0] -= 1
            raise subprocess.CalledProcessError(3, argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(installer.subprocess, "run", fail_first_bootstrap)
    with pytest.raises(subprocess.CalledProcessError):
        installer._install_transaction(paths, fake_bundles(tmp_path / "v2", "new"), None, home)

    assert (paths["app"] / "Contents/MacOS/PowerPointArchiveAgent").read_bytes() == old_app
    assert (paths["cli"] / "pptviewer").read_bytes() == old_cli
    assert paths["plist"].read_bytes() == old_plist
    assert [c for c in calls if "bootstrap" in c][-1][1] == "bootstrap"
    assert not list(home.rglob(".pptviewer-*-backup-*"))


def test_uninstall_preserves_config_archive_logs_and_is_idempotent(installer, monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    paths = installer.mac_paths(home)
    source = tmp_path / "slides"
    source.mkdir()
    fake_launch(installer, monkeypatch, home)
    installer._install_transaction(paths, fake_bundles(tmp_path / "v1", "old"), source, home)
    archive = paths["config"].parent / "archive"
    archive.mkdir()
    (archive / "index.db").write_bytes(b"index")
    (paths["logs"] / "agent.log").write_bytes(b"logs")

    installer._uninstall_transaction(paths)
    installer._uninstall_transaction(paths)
    assert not paths["app"].exists()
    assert not paths["cli"].exists()
    assert not paths["plist"].exists()
    assert paths["config"].is_file()
    assert (archive / "index.db").read_bytes() == b"index"
    assert (paths["logs"] / "agent.log").read_bytes() == b"logs"


def test_refuses_uninstall_of_foreign_launchagent(installer, monkeypatch, tmp_path):
    paths = installer.mac_paths(tmp_path)
    paths["plist"].parent.mkdir(parents=True, exist_ok=True)
    paths["plist"].write_bytes(plistlib.dumps({"Label": "someone.else"}))
    paths["app"].mkdir(parents=True)
    with pytest.raises(RuntimeError, match="unrelated LaunchAgent"):
        installer._uninstall_transaction(paths)
    assert paths["app"].exists()


def test_install_rejects_missing_initial_scan_root(installer, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    paths = installer.mac_paths(home)
    with pytest.raises(ValueError, match="root"):
        installer._install_transaction(paths, fake_bundles(tmp_path / "v1", "new"), None, home)


def test_install_preserves_native_app_symlinks(installer, monkeypatch, tmp_path):
    """PyInstaller app bundles often contain symlinked macOS frameworks."""
    home = tmp_path / "home"
    home.mkdir()
    source = tmp_path / "slides"
    source.mkdir()
    bundle = fake_bundles(tmp_path / "v1", "bundle")
    framework_dir = bundle / installer.APP_NAME / "Contents/Frameworks"
    framework_dir.mkdir()
    (framework_dir / "libcore.dylib").write_bytes(b"native placeholder")
    (framework_dir / "current.dylib").symlink_to("libcore.dylib")
    fake_launch(installer, monkeypatch, home)
    installer._install_transaction(installer.mac_paths(home), bundle, source, home)
    installed = installer.mac_paths(home)["app"] / "Contents/Frameworks/current.dylib"
    assert installed.is_symlink()
    assert installed.read_bytes() == b"native placeholder"
