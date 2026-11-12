"""Portable validation for the prepared macOS app and LaunchAgent sources."""
from __future__ import annotations

import importlib.util
import json
import plistlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


preflight = _load("mac_preflight", ROOT / "scripts/preflight_macos_package.py")
installer = _load("mac_installer", ROOT / "packaging/macos/install_agent.py")


def test_mac_source_preflight_passes_with_native_acceptance_pending():
    output = preflight.checks(ROOT)
    assert len(output) >= 12
    assert all(item["status"] == "pass" for item in output if item["name"] != "built_mac_artifacts")
    assert next(item for item in output if item["name"] == "built_mac_artifacts")["status"] == "warning"


def test_mac_source_preflight_fails_on_missing_asset(tmp_path):
    results = preflight.checks(tmp_path)
    assert results == [{
        "name": "source_files", "status": "fail",
        "detail": "Required backend, bundle, launch, and UI files exist",
    }]


def test_mac_app_and_cli_artifacts_are_only_header_checked(tmp_path):
    artifact_app = tmp_path / "PowerPointArchiveAgent.app/Contents/MacOS/PowerPointArchiveAgent"
    artifact_cli = tmp_path / "pptviewer/pptviewer"
    artifact_app.parent.mkdir(parents=True)
    artifact_cli.parent.mkdir(parents=True)
    artifact_app.write_bytes(b"\xcf\xfa\xed\xfe" + b"placeholder")
    artifact_cli.write_bytes(b"\xcf\xfa\xed\xfe" + b"placeholder")
    results = preflight.checks(ROOT, artifacts=tmp_path)
    assert all(v["status"] == "pass" for v in results)
    artifact_cli.write_bytes(b"not a binary")
    assert any(v["status"] == "fail" for v in preflight.checks(ROOT, artifacts=tmp_path))


def test_installer_plan_and_launchagent_plist_are_safe(tmp_path):
    home = tmp_path / "mac-home"
    build = tmp_path / "dist"
    before = list(tmp_path.rglob("*"))
    preview = installer.plan(home, build, tmp_path / "slides")
    assert not preview["app_artifact_available"]
    assert "Library/Application Support" in preview["configuration"]
    assert preview["requires_macos_acceptance"]
    plist = installer.create_plist(home)
    assert plist["RunAtLoad"] is True and plist["KeepAlive"] is True
    assert plist["ProgramArguments"][0].endswith("/PowerPointArchiveAgent.app/Contents/MacOS/PowerPointArchiveAgent")
    assert "LaunchAgents" in preview["launch_agent"]
    assert plistlib.loads(plistlib.dumps(plist)) == plist
    assert list(tmp_path.rglob("*")) == before
    assert installer.main(["--plan", "--home", str(home), "--artifacts", str(build)]) == 0


def test_install_mutation_refused_on_non_macos(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "sys", type("FakeSys", (), {"platform": "linux"})())
    import pytest
    with pytest.raises(RuntimeError, match="real macOS"):
        installer.install(tmp_path, tmp_path, None)


def test_non_macos_build_script_fails_without_writing(tmp_path):
    if sys.platform == "darwin":
        return
    script = ROOT / "packaging/macos/build.sh"
    completed = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=4)
    assert completed.returncode == 2
    assert "macOS machine is required" in completed.stderr
