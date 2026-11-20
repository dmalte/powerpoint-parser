"""Readiness report tests: no automation launch and no private paths in output."""
from __future__ import annotations

import importlib.util
import json
import plistlib
import sys
from pathlib import Path

import pytest

from ppt_visual_archive.config import default_config, save_config


@pytest.fixture
def diagnostic():
    path = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_macos.py"
    spec = importlib.util.spec_from_file_location("mac_diagnostics_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def valid(tmp_path):
    home = tmp_path / "private-personal-username"
    home.mkdir()
    source = home / "confidential-presentation-files"
    source.mkdir()
    archive = home / "viewer"
    archive.mkdir()
    config = default_config(str(archive), [str(source)])
    path = home / "config.yaml"
    save_config(config, path)
    return home, path, source, archive


def _statuses(result):
    return {check["name"]: check["status"] for check in result["checks"]}


def test_valid_config_and_dependency_report_is_path_free(diagnostic, valid):
    home, config, source, archive = valid
    before = sorted(str(p) for p in home.rglob("*"))
    report = diagnostic.check_readiness(config, home=home, platform_name="darwin")
    after = sorted(str(p) for p in home.rglob("*"))
    assert after == before
    assert _statuses(report)["configuration"] == "pass"
    assert _statuses(report)["scan_roots"] == "pass"
    assert _statuses(report)["archive_writable"] == "pass"
    assert _statuses(report)["automation_permission"] == "unverified"
    contents = json.dumps(report)
    assert str(home) not in contents
    assert "confidential-presentation" not in contents
    assert "personal-username" not in contents
    assert "config.yaml" not in contents


def test_bad_config_and_missing_roots_are_reported_without_throwing(diagnostic, valid):
    home, config, source, archive = valid
    config.write_text("invalid: [broken yaml\n")
    result = diagnostic.check_readiness(config, home=home, platform_name="linux")
    assert _statuses(result)["configuration"] == "warning"
    assert _statuses(result)["native_macos"] == "unverified"
    assert result["counts"]["fail"] == 0
    data = default_config(str(archive), [str(source / "not-present")])
    save_config(data, config, overwrite=True)
    invalid = diagnostic.check_readiness(config, home=home, platform_name="darwin")
    assert _statuses(invalid)["scan_roots"] == "fail"


def test_foreign_and_correct_launchagent_label(diagnostic, valid):
    home, config, source, archive = valid
    app = home / "Applications/PowerPointArchiveAgent.app/Contents/MacOS/PowerPointArchiveAgent"
    app.parent.mkdir(parents=True)
    app.write_bytes(b"some executable")
    plist = home / "Library/LaunchAgents/uk.pptvisualarchive.agent.plist"
    plist.parent.mkdir(parents=True)
    plist.write_bytes(plistlib.dumps({"Label": "foreign.agent", "ProgramArguments": [str(app)]}))
    assert _statuses(diagnostic.check_readiness(config, home=home))["launchagent"] == "fail"
    plist.write_bytes(plistlib.dumps({
        "Label": "uk.pptvisualarchive.agent", "RunAtLoad": True,
        "ProgramArguments": [str(app)],
    }))
    report = diagnostic.check_readiness(config, home=home)
    assert _statuses(report)["installed_app"] == "pass"
    assert _statuses(report)["launchagent"] == "pass"


def test_diagnostic_cli_local_json_is_not_automatically_uploaded(diagnostic, valid, capsys, tmp_path):
    home, config, source, archive = valid
    report = diagnostic.check_readiness(config, home=home)
    assert report["counts"]["unverified"] >= 3
    output = tmp_path / "report.json"
    assert diagnostic.main(["--config", str(config), "--json", str(output)]) in (0, 1)
    data = json.loads(output.read_text(encoding="utf-8"))
    assert "checks" in data
    assert not any("file_path" in item for item in data["checks"])
    assert str(source) not in output.read_text(encoding="utf-8")
