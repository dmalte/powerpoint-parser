"""Cross-platform static macOS packaging preflight (no macOS execution).

Usage:
    python scripts/preflight_macos_package.py
    python scripts/preflight_macos_package.py --artifacts dist --json .runtime/macos-preflight.json

A green result certifies only source structure and optional artifact signatures,
not PowerPoint AppleScript, Automation permissions, launchctl or package behavior.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "packaging/macos/PowerPointVisualArchive.spec",
    "packaging/macos/build.sh",
    "packaging/macos/install_agent.py",
    "packaging/windows/agent_launcher.py",
    "packaging/windows/pptviewer_launcher.py",
    "src/ppt_visual_archive/mac_renderer.py",
    "src/ppt_visual_archive/renderer_factory.py",
    "web/templates/index.html.j2",
    "web/templates/settings.html.j2",
    "web/static/js/app.js",
    "web/static/js/performance.js",
    "web/static/css/style.css",
)


def checks(root: Path = ROOT, artifacts: Path | None = None) -> list[dict]:
    results = []

    def add(name: str, value: bool, info: str, optional=False):
        results.append({
            "name": name, "status": "pass" if value else ("warning" if optional else "fail"),
            "detail": info,
        })

    missing = [relative for relative in SOURCE_FILES if not (root / relative).is_file()]
    add("source_files", not missing, "Required backend, bundle, launch, and UI files exist")
    if missing:
        return results
    spec = (root / SOURCE_FILES[0]).read_text()
    build = (root / SOURCE_FILES[1]).read_text()
    installer = (root / SOURCE_FILES[2]).read_text()
    renderer = (root / "src/ppt_visual_archive/mac_renderer.py").read_text()
    factory = (root / "src/ppt_visual_archive/renderer_factory.py").read_text()

    for path in ("packaging/macos/PowerPointVisualArchive.spec",
                 "packaging/macos/install_agent.py",
                 "src/ppt_visual_archive/mac_renderer.py",
                 "src/ppt_visual_archive/renderer_factory.py"):
        try:
            ast.parse((root / path).read_text())
        except SyntaxError:
            add("syntax:" + Path(path).name, False, "Python source or PyInstaller spec syntax")
        else:
            add("syntax:" + Path(path).name, True, "Python source or PyInstaller spec syntax")

    add("bundled_frontend", 'datas=[(str(web_root), "web")]' in spec and
        'name="PowerPointArchiveAgent.app"' in spec and 'console=False' in spec,
        "GUI app bundle contains source templates/scripts and uses windowless agent")
    add("bundle_cli", 'name="pptviewer"' in spec and 'console=True' in spec,
        "Separate support console executable included")
    add("mac_automation_description", "NSAppleEventsUsageDescription" in spec,
        "App bundle explains Microsoft PowerPoint Automation request")
    add("user_session_install", all(text in installer for text in (
        '"launchctl", "bootstrap"', '"launchctl", "bootout"', 'gui/{uid}',
        "Library", "LaunchAgents", "KeepAlive", "RunAtLoad")),
        "Installer plans a per-user LaunchAgent, not a privileged daemon")
    add("config_preservation", 'if not paths["config"].exists():' in installer and
        '"init-config"' in installer,
        "Per-user YAML survives repeated installations")
    add("explicit_install", 'group.add_argument("--install"' in installer and
        'sys.platform != "darwin"' in installer,
        "Non-Mac plan is safe; mutating installation requires explicit flag and macOS")
    add("build_native_only", 'uname -s' in build and '"Darwin"' in build and
        'scripts/preflight_macos_package.py' in build and "sudo " not in build,
        "Build runs only on Mac; static check precedes build")
    add("conversion_contract", "POWERPOINT_PDF_APPLESCRIPT" in renderer and
        '"osascript"' in renderer and 'extract_and_render_pdf' in renderer and
        "TemporaryDirectory" in renderer and '"pdf:impress_pdf_Export"' in renderer,
        "Mac converter produces existing images through ephemeral PDF; optional LibreOffice")
    add("platform_selection", all(x in factory for x in (
        'platform == "win32"', 'platform == "darwin"', 'backend == "libreoffice"')),
        "Windows COM remains distinct; Mac PowerPoint and explicit fallback supported")
    if artifacts is None:
        add("built_mac_artifacts", False, "Native macOS .app and CLI not built or checked on Pi", optional=True)
    else:
        expected = [
            artifacts / "PowerPointArchiveAgent.app/Contents/MacOS/PowerPointArchiveAgent",
            artifacts / "pptviewer/pptviewer",
        ]
        for executable in expected:
            try:
                with executable.open("rb") as fd:
                    signature = fd.read(4)
                valid = signature in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf")
            except OSError:
                valid = False
            add("artifact:" + executable.name, valid, "Mach-O header and expected file present")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    values = checks(args.root, args.artifacts)
    failed = sum(v["status"] == "fail" for v in values)
    warning = sum(v["status"] == "warning" for v in values)
    payload = {
        "schema_version": 1,
        "kind": "static macOS preparation preflight",
        "checks": values,
        "passed": len(values) - failed - warning,
        "failed": failed,
        "warnings": warning,
        "macos_native_automation": "NOT_TESTED",
        "macos_application_build": "NOT_TESTED",
        "macos_user_login": "NOT_TESTED",
        "status": "pass" if not failed else "fail",
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"macOS packaging source preflight: {payload['status']} "
          f"({payload['passed']} pass, {failed} fail, {warning} warning)")
    for item in values:
        if item["status"] != "pass":
            print(item["status"].upper() + " " + item["name"] + ": " + item["detail"])
    print("Actual PowerPoint-for-Mac automation / login / native bundle: NOT TESTED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
