"""Local, path-free readiness diagnostics for PowerPoint Visual Archive on Mac.

Run on any machine (including Pi) without launching PowerPoint or changing TCC:
    python scripts/diagnose_macos.py --config ~/.local/share/.../config.yaml
    python scripts/diagnose_macos.py --json .runtime/macos-diagnostics.json

A static preflight is not proof of working AppleScript, Automation consent,
bundled Mac code signing/notarization, visual fidelity, or LoginAgent startup.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import plistlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from ppt_visual_archive.config import load_config
from ppt_visual_archive.platform_paths import default_config_path

LABEL = "uk.pptvisualarchive.agent"
MIN_FREE_MB = 512


def check_readiness(config_path: Path, *, home: Path | None = None,
                    platform_name: str | None = None) -> dict:
    home = Path.home() if home is None else home
    platform = sys.platform if platform_name is None else platform_name
    checks: list[dict] = []

    def note(name: str, status: str, description: str) -> None:
        if status not in {"pass", "warning", "fail", "unverified"}:
            raise ValueError(status)
        checks.append({"name": name, "status": status, "detail": description})

    note("native_macos", "pass" if platform == "darwin" else "unverified",
         "Native macOS required for functional PowerPoint/LaunchAgent acceptance")
    note("python_pptx", "pass" if importlib.util.find_spec("pptx") else "fail",
         "Original presentation text/notes extraction dependency")
    note("pymupdf", "pass" if importlib.util.find_spec("fitz") else "fail",
         "PDF-to-slide JPEG rendering dependency")

    config = None
    try:
        config = load_config(config_path)
    except (OSError, ValueError, TypeError, AttributeError):
        note("configuration", "warning", "Configuration is absent or could not be parsed")
    else:
        note("configuration", "pass", "Existing configuration parsed")
        backend = config.render.mac_pptx_backend.strip().lower()
        if backend not in {"powerpoint", "libreoffice"}:
            note("renderer_backend", "fail", "Unknown Mac PPTX renderer selection")
        else:
            note("renderer_backend", "pass", "Configured PPTX renderer selection is supported")
        if backend == "powerpoint":
            note("osascript", "pass" if shutil.which("osascript") else "warning",
                 "macOS AppleScript command availability; does not verify permissions")
            powerpoint_apps = (
                Path("/Applications/Microsoft PowerPoint.app"),
                home / "Applications" / "Microsoft PowerPoint.app",
            )
            note("powerpoint_app", "pass" if any(x.is_dir() for x in powerpoint_apps) else "warning",
                 "PowerPoint for Mac app bundle presence")
        elif backend == "libreoffice":
            executable = shutil.which("soffice") or shutil.which("libreoffice")
            candidate = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
            note("libreoffice", "pass" if executable or candidate.is_file() else "warning",
                 "Explicit LibreOffice backend executable presence")
        roots = [Path(root) for root in config.scan_roots]
        if not roots:
            note("scan_roots", "fail", "No scan roots configured")
        else:
            valid = all(path.is_dir() and os.access(path, os.R_OK | os.X_OK) for path in roots)
            note("scan_roots", "pass" if valid else "fail",
                 "Configured scan folder count: " + str(len(roots)) + "; all must be readable")
        if config.output_dir:
            output = Path(config.output_dir)
            parent = output
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            valid = parent.is_dir() and os.access(parent, os.W_OK | os.X_OK)
            note("archive_writable", "pass" if valid else "fail",
                 "Archive directory or existing parent permits writing")
            try:
                free = shutil.disk_usage(parent).free / 1048576
                note("free_disk", "pass" if free >= MIN_FREE_MB else "warning",
                     "At least 512 MiB free for temporary rendering and archive generation")
            except OSError:
                note("free_disk", "warning", "Available storage could not be determined")
        else:
            note("archive_writable", "fail", "Archive output directory not configured")

    app = home / "Applications" / "PowerPointArchiveAgent.app" / "Contents" / "MacOS" / "PowerPointArchiveAgent"
    note("installed_app", "pass" if app.is_file() else "warning",
         "Per-user built agent executable presence")
    plist = home / "Library" / "LaunchAgents" / (LABEL + ".plist")
    if not plist.is_file():
        note("launchagent", "warning", "Per-user LaunchAgent plist not installed")
    else:
        try:
            content = plistlib.loads(plist.read_bytes())
            valid = content.get("Label") == LABEL and content.get("RunAtLoad") is True
            args = content.get("ProgramArguments") or []
            valid = valid and bool(args) and Path(args[0]) == app
            note("launchagent", "pass" if valid else "fail",
                 "Per-user LaunchAgent plist has expected label, executable and startup policy")
        except (OSError, ValueError, TypeError, plistlib.InvalidFileException):
            note("launchagent", "fail", "LaunchAgent plist is unreadable or malformed")

    note("automation_permission", "unverified",
         "macOS TCC permission requires interactive PowerPoint/AppleScript acceptance")
    note("visual_fidelity", "unverified",
         "Slide images require comparison against native PowerPoint on macOS")
    note("bundle_signature", "unverified",
         "Code signing, Gatekeeper and notarization require a native Mac build")

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "local non-executing diagnostic",
        "checks": checks,
        "counts": {
            "pass": sum(c["status"] == "pass" for c in checks),
            "warning": sum(c["status"] == "warning" for c in checks),
            "fail": sum(c["status"] == "fail" for c in checks),
            "unverified": sum(c["status"] == "unverified" for c in checks),
        },
        "privacy": "No scan paths, document names, account names or contents are included",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--json", type=Path, help="Write an explicitly requested local JSON report")
    args = parser.parse_args(argv)
    report = check_readiness(args.config or default_config_path())
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    counts = report["counts"]
    print("macOS readiness:", ", ".join(f"{k}={v}" for k, v in counts.items()))
    for item in report["checks"]:
        if item["status"] != "pass":
            print(item["status"].upper(), item["name"], "—", item["detail"])
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
