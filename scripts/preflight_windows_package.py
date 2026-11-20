"""Offline cross-platform preflight for the Windows per-user installer.

Run: python scripts/preflight_windows_package.py
Optional: python scripts/preflight_windows_package.py --artifacts dist --version 0.1.4

A PASS means source packaging definitions are consistent; it does NOT mean
a Windows installer has been built, run, signed, or validated with PowerPoint.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _check_pe(path: Path) -> bool:
    """Minimal PE-signature test, not executable execution or signature trust."""
    try:
        with path.open("rb") as stream:
            dos = stream.read(64)
            if len(dos) < 64 or dos[:2] != b"MZ":
                return False
            offset = struct.unpack_from("<I", dos, 0x3c)[0]
            if offset < 64 or offset > 4 * 1024 * 1024:
                return False
            stream.seek(offset)
            return stream.read(4) == b"PE\x00\x00"
    except OSError:
        return False


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _version(pattern: str, data: str, label: str) -> str:
    match = re.search(pattern, data, flags=re.MULTILINE)
    if not match:
        raise ValueError("Could not find default version in " + label)
    return match.group(1)


def evaluate(root: Path = ROOT, *, version: str | None = None, artifacts: Path | None = None, skip_installer: bool = False) -> dict:
    checks: list[dict] = []

    def check(identifier: str, condition: bool, description: str, *, warning: bool = False):
        checks.append({
            "id": identifier,
            "status": "pass" if condition else ("warning" if warning else "fail"),
            "description": description,
        })

    pkg_dir = root / "packaging" / "windows"
    expected_inputs = (
        "pyproject.toml",
        "packaging/windows/PowerPointVisualArchive.spec",
        "packaging/windows/PowerPointVisualArchive.iss",
        "packaging/windows/build.ps1",
        "packaging/windows/pptviewer_launcher.py",
        "packaging/windows/agent_launcher.py",
        "web/templates/index.html.j2",
        "web/templates/settings.html.j2",
        "web/static/js/app.js",
        "web/static/js/settings.js",
        "web/static/js/performance.js",
        "web/static/js/agent-status.js",
        "web/static/css/style.css",
        "web/static/loading.html",
    )
    missing = [name for name in expected_inputs if not (root / name).is_file()]
    check("required-inputs", not missing,
          "Required project, launchers, web assets and installer definitions exist")
    if missing:
        return _report(checks, details={"missing_input_count": len(missing)}, artifacts_requested=artifacts is not None)

    spec = _read(root, "packaging/windows/PowerPointVisualArchive.spec")
    iss = _read(root, "packaging/windows/PowerPointVisualArchive.iss")
    build = _read(root, "packaging/windows/build.ps1")
    pyproject = _read(root, "pyproject.toml")

    try:
        ast.parse(spec)
        spec_syntax = True
    except SyntaxError:
        spec_syntax = False
    check("pyinstaller-spec-syntax", spec_syntax, "PyInstaller spec is valid Python syntax")
    check("frozen-assets", 'datas=[(str(web_root), "web")]' in spec and 'project_root = Path(SPECPATH).parents[1]' in spec,
          "The frozen bundle includes the complete web template/static directory")
    check("two-executable-build", all(piece in spec for piece in (
        'name="pptviewer"', 'name="PowerPointArchiveAgent"', 'console=False', 'console=True',
        'pptviewer_launcher.py', 'agent_launcher.py', 'hiddenimports=hidden_imports',
    )), "PyInstaller declares console support and a windowless per-user agent")
    check("windows-com-imports", all(name in spec for name in (
        '"pythoncom"', '"pywintypes"', '"win32com.client"', '"win32gui"',
    )), "Windows COM and notification-area modules are included in hidden imports")
    check("conditional-win32", bool(re.search(
        'pywin32[^"\\n]*;\\s*platform_system\\s*==\\s*[\'\\\'"]Windows[\'\\\'"]', pyproject
    )), "pywin32 is a Windows-only dependency, preserving PDF-only non-Windows use")

    for file in ("pptviewer_launcher.py", "agent_launcher.py"):
        source = _read(root, "packaging/windows/" + file)
        try:
            ast.parse(source)
            valid = "from ppt_visual_archive.cli import main" in source and '__main__' in source
            if file == "agent_launcher.py":
                valid = valid and 'main(args=["agent", *sys.argv[1:]])' in source
        except SyntaxError:
            valid = False
        check("launcher-" + file.removesuffix(".py"), valid,
              "The " + file + " launcher imports the project CLI and uses the intended entrypoint")

    check("installer-per-user", all(piece in iss for piece in (
        "PrivilegesRequired=lowest", "{localappdata}", "ArchitecturesAllowed=x64compatible",
    )) and "PrivilegesRequired=admin" not in iss,
          "Inno Setup installs without admin privileges into user app data")
    check("installer-runtime-and-startup", all(piece in iss for piece in (
        'Source: "..\\..\\dist\\pptviewer.exe"',
        'Source: "..\\..\\dist\\PowerPointArchiveAgent.exe"',
        '{userstartup}\\PowerPoint Visual Archive',
        "PowerPointArchiveAgent.exe",
    )), "Installer includes both executables and registers logon startup")
    # Inno's Restart Manager must close a *stale* installed windowless agent
    # before replacing its EXE. Only the two bundled EXEs are in scope: never
    # close the separately managed source/dev pythonw.exe or restart old code.
    check("installer-upgrade-process-handling", all(re.search(pattern, iss, flags=re.MULTILINE) for pattern in (
        r"^CloseApplications=force$",
        r"^CloseApplicationsFilter=PowerPointArchiveAgent\.exe,pptviewer\.exe$",
        r"^RestartApplications=no$",
        r"^PrivilegesRequired=lowest$",
    )), "Upgrade closes unresponsive installed EXEs via Restart Manager without closing dev agent or restarting stale binaries")

    check("installer-config-preservation", all(piece in iss for piece in (
        "Check: not ConfigExists", "FileExists(ConfigPath)", "init-config --root",
        "ShouldSkipPage", "GetScanRoot",
    )), "First install selects scan root while upgrades preserve existing YAML config")

    try:
        project_ver = _version('^version\\s*=\\s*"([^"]+)"', pyproject, "pyproject.toml")
        build_ver = _version('^\\s*\\[string\\]\\$Version\\s*=\\s*"([^"]+)"', build, "build.ps1")
        iss_ver = _version('^#define AppVersion "([^"]+)"', iss, "Inno Setup")
        expected = version or project_ver
        versions_ok = all(v == expected for v in (project_ver, build_ver, iss_ver))
    except ValueError:
        versions_ok = False
        expected = version or "unknown"
    check("versions-consistent", versions_ok,
          "Package, build helper and installer default versions agree (X.Y.Z)")
    check("build-exit-checks", all(piece in build for piece in (
        "if ($LASTEXITCODE -ne 0)", "Python environment creation failed",
        "Dependency installation failed", "PyInstaller failed", "Inno Setup failed",
        "did not produce the expected executables", "did not produce the expected installer",
        "Test-Path $InstallerPath",
    )), "PowerShell helper checks native tool exit codes and output artifacts")
    check("build-version-validation", '^[0-9]+\\.[0-9]+\\.[0-9]+$' in build,
          "PowerShell build script rejects invalid release versions")

    if artifacts is not None:
        expected_binaries = [artifacts / "pptviewer.exe", artifacts / "PowerPointArchiveAgent.exe"]
        if not skip_installer:
            expected_binaries.append(artifacts / "installer" / f"PowerPointVisualArchiveSetup-{expected}.exe")
        for file in expected_binaries:
            check("artifact-" + file.name, _check_pe(file),
                  "Expected Windows artifact has a minimal valid PE signature")
    else:
        check("windows-artifacts", False,
              "Not checked: no Windows-generated artifacts supplied", warning=True)
    return _report(checks, details={"declared_version": expected}, artifacts_requested=artifacts is not None)


def _report(checks: list[dict], *, details: dict, artifacts_requested: bool) -> dict:
    failures = sum(item["status"] == "fail" for item in checks)
    warnings = sum(item["status"] == "warning" for item in checks)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "static-source-and-optional-artifact-preflight",
        "result": "fail" if failures else "pass",
        "checks": checks,
        "summary": {"passed": len(checks) - failures - warnings, "failed": failures, "warnings": warnings},
        "artifacts_checked": artifacts_requested,
        "details": details,
        "not_verified": [
            "Windows build execution", "Windows install/upgrade/uninstall",
            "PowerPoint COM rendering", "User-logon startup and tray controls",
            "Code signing", "Real-platform performance",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--artifacts", type=Path, help="Folder holding Windows-built EXEs and installer")
    parser.add_argument("--version", help="Expected X.Y.Z release version (defaults to pyproject)")
    parser.add_argument("--json", type=Path, help="Write a local JSON report")
    parser.add_argument("--skip-installer", action="store_true", help="Check only the two application EXEs")
    args = parser.parse_args(argv)
    if args.version and not re.fullmatch('[0-9]+\\.[0-9]+\\.[0-9]+', args.version):
        parser.error("--version must be numeric X.Y.Z")
    report = evaluate(args.root, version=args.version, artifacts=args.artifacts, skip_installer=args.skip_installer)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Windows preflight: {report['result'].upper()} ({report['summary']})")
    for item in report["checks"]:
        print(f"  {item['status'].upper():7s} {item['id']}: {item['description']}")
    print("Windows smoke validation: NOT PERFORMED")
    return 0 if report["result"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
