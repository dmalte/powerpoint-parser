"""Prepare/install an optional per-user macOS LaunchAgent (not a LaunchDaemon).

On Pi, --plan only renders a path-free deployment plan and plist structure.
On a signed-in Mac, --install explicitly copies an existing PyInstaller app,
sets up configuration if needed, and bootstraps a user LaunchAgent. No sudo.
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

LAUNCH_LABEL = "uk.pptvisualarchive.agent"
APP_NAME = "PowerPointArchiveAgent.app"


def mac_paths(home: Path) -> dict[str, Path]:
    home = home.resolve()
    return {
        "app": home / "Applications" / APP_NAME,
        "cli": home / "Library" / "Application Support" / "PowerPointVisualArchive" / "bin" / "pptviewer",
        "config": home / "Library" / "Application Support" / "PowerPointVisualArchive" / "config.yaml",
        "logs": home / "Library" / "Logs" / "PowerPointVisualArchive",
        "plist": home / "Library" / "LaunchAgents" / (LAUNCH_LABEL + ".plist"),
    }


def create_plist(home: Path) -> dict:
    paths = mac_paths(home)
    return {
        "Label": LAUNCH_LABEL,
        "ProgramArguments": [str(paths["app"] / "Contents" / "MacOS" / "PowerPointArchiveAgent")],
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(paths["logs"] / "launchagent-stdout.log"),
        "StandardErrorPath": str(paths["logs"] / "launchagent-stderr.log"),
    }


def plan(home: Path, artifacts: Path, scan_root: Path | None) -> dict:
    paths = mac_paths(home)
    return {
        "platform": "macOS",
        "launch_kind": "per-user-LaunchAgent",
        "app_path": str(paths["app"]),
        "support_cli_path": str(paths["cli"]),
        "configuration": str(paths["config"]),
        "launch_agent": str(paths["plist"]),
        "scan_root": str(scan_root.resolve()) if scan_root else None,
        "app_artifact_available": (artifacts / APP_NAME / "Contents/MacOS/PowerPointArchiveAgent").is_file(),
        "cli_artifact_available": (artifacts / "pptviewer" / "pptviewer").is_file(),
        "requires_macos_acceptance": True,
    }


def install(home: Path, artifacts: Path, scan_root: Path | None) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("Per-user installation and launchctl require a real macOS machine")
    if not scan_root or not scan_root.is_dir():
        raise ValueError("A local --root presentation folder is required for installation")
    paths = mac_paths(home)
    app_artifact = artifacts / APP_NAME
    cli_artifact = artifacts / "pptviewer"
    if not (app_artifact / "Contents/MacOS/PowerPointArchiveAgent").is_file():
        raise FileNotFoundError("Mac app build artifact is missing")
    if not (cli_artifact / "pptviewer").is_file():
        raise FileNotFoundError("Mac console build artifact is missing")

    paths["app"].parent.mkdir(parents=True, exist_ok=True)
    paths["cli"].parent.mkdir(parents=True, exist_ok=True)
    paths["logs"].mkdir(parents=True, exist_ok=True)
    paths["plist"].parent.mkdir(parents=True, exist_ok=True)

    # Copy only user files; no sudo and no global app/services.
    # A first install has no previous app to overwrite.
    shutil.copytree(app_artifact, paths["app"], dirs_exist_ok=True)
    shutil.copytree(cli_artifact, paths["cli"], dirs_exist_ok=True)
    if not paths["config"].exists():
        subprocess.run(
            [str(paths["cli"] / "pptviewer"), "init-config", "--root", str(scan_root), "--include-pdf"],
            check=True,
        )

    uid = os.getuid()
    if paths["plist"].exists():
        # Ignore "not currently bootstrapped"; do not remove unrelated services.
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(paths["plist"])],
            check=False, capture_output=True,
        )
    paths["plist"].write_bytes(plistlib.dumps(create_plist(home)))
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(paths["plist"])], check=True)
    print("Installed per-user macOS agent. Native PowerPoint Automation consent may be requested.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=Path("dist"))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--root", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--plan", action="store_true", help="Show install plan only (default)")
    group.add_argument("--install", action="store_true", help="Actually install on signed-in Mac")
    args = parser.parse_args(argv)
    if args.install:
        install(args.home, args.artifacts, args.root)
    else:
        print(json.dumps(plan(args.home, args.artifacts, args.root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
