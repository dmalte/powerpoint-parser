"""Portable Windows packaging preflight tests; no Windows installer is executed."""
from __future__ import annotations

import importlib.util
import json
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("windows_preflight", ROOT / "scripts/preflight_windows_package.py")
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader
SPEC.loader.exec_module(module)


def checks(root=ROOT, **kwargs):
    return {item["id"]: item for item in module.evaluate(root, **kwargs)["checks"]}


def copy_inputs(target):
    shutil.copytree(ROOT / "packaging", target / "packaging")
    shutil.copytree(ROOT / "web", target / "web")
    (target / "pyproject.toml").write_bytes((ROOT / "pyproject.toml").read_bytes())


def test_actual_source_preflight_passes_but_does_not_claim_windows_validation():
    report = module.evaluate(ROOT)
    assert report["result"] == "pass"
    assert report["summary"]["failed"] == 0
    assert report["summary"]["warnings"] == 1  # Windows-built artifacts absent.
    assert "Windows install/upgrade/uninstall" in report["not_verified"]
    assert "PowerPoint COM rendering" in report["not_verified"]


def test_preflight_rejects_tampered_bundle_and_missing_assets(tmp_path):
    copy_inputs(tmp_path)
    spec = tmp_path / "packaging/windows/PowerPointVisualArchive.spec"
    spec.write_text(spec.read_text(encoding="utf-8").replace('datas=[(str(web_root), "web")]', "datas=[]"))
    assert checks(tmp_path)["frozen-assets"]["status"] == "fail"
    (tmp_path / "web/static/js/performance.js").unlink()
    assert checks(tmp_path)["required-inputs"]["status"] == "fail"


def test_preflight_rejects_unsafe_install_and_bad_version(tmp_path):
    copy_inputs(tmp_path)
    installer = tmp_path / "packaging/windows/PowerPointVisualArchive.iss"
    installer.write_text(installer.read_text(encoding="utf-8").replace("PrivilegesRequired=lowest", "PrivilegesRequired=admin"))
    result = checks(tmp_path, version="1.2.3")
    assert result["installer-per-user"]["status"] == "fail"
    assert result["versions-consistent"]["status"] == "fail"


def _fake_pe():
    """Minimal valid DOS and PE signatures for structural checks, not a real EXE."""
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 128)
    data[128:132] = b"PE\x00\x00"
    return bytes(data)


def test_artifact_checks_validate_pe_header_and_skip_installer(tmp_path):
    (tmp_path / "installer").mkdir()
    for file in ("pptviewer.exe", "PowerPointArchiveAgent.exe",
                 "installer/PowerPointVisualArchiveSetup-0.1.4.exe"):
        (tmp_path / file).write_bytes(_fake_pe())
    result = checks(ROOT, artifacts=tmp_path)
    assert all(result["artifact-" + name]["status"] == "pass" for name in (
        "pptviewer.exe", "PowerPointArchiveAgent.exe", "PowerPointVisualArchiveSetup-0.1.4.exe"))
    (tmp_path / "pptviewer.exe").write_bytes(b"not an executable")
    assert checks(ROOT, artifacts=tmp_path)["artifact-pptviewer.exe"]["status"] == "fail"
    (tmp_path / "installer/PowerPointVisualArchiveSetup-0.1.4.exe").unlink()
    skip = checks(ROOT, artifacts=tmp_path, skip_installer=True)
    assert "artifact-PowerPointVisualArchiveSetup-0.1.4.exe" not in skip


def test_cli_json_output_and_missing_artifacts(tmp_path):
    report_file = tmp_path / "preflight.json"
    assert module.main(["--root", str(ROOT), "--json", str(report_file)]) == 0
    data = json.loads(report_file.read_text(encoding="utf-8"))
    assert data["result"] == "pass"
    assert "PowerPoint COM rendering" in data["not_verified"]
    assert module.main(["--root", str(ROOT), "--artifacts", str(tmp_path)]) == 1


def test_windows_build_discovers_inno_setup_seven_without_path():
    build = (ROOT / "packaging/windows/build.ps1").read_text(encoding="utf-8")
    assert "Inno Setup $Major" in build
    assert "@(7, 6)" in build
    assert "ISCC.exe" in build
    assert "Test-Path $Candidate" in build
    assert '"Inno Setup failed' in build


def test_preflight_rejects_unsafe_installer_upgrade_shutdown(tmp_path):
    copy_inputs(tmp_path)
    script = tmp_path / "packaging/windows/PowerPointVisualArchive.iss"
    original = script.read_text(encoding="utf-8")
    assert checks(tmp_path)["installer-upgrade-process-handling"]["status"] == "pass"
    for before, after in (
        ("CloseApplications=force", "CloseApplications=yes"),
        ("CloseApplicationsFilter=PowerPointArchiveAgent.exe,pptviewer.exe", "CloseApplicationsFilter=*.exe"),
        ("RestartApplications=no", "RestartApplications=yes"),
    ):
        script.write_text(original.replace(before, after), encoding="utf-8")
        assert checks(tmp_path)["installer-upgrade-process-handling"]["status"] == "fail"
