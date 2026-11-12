"""Per-user macOS agent installation lifecycle, safe to inspect on Raspberry Pi.

Explicit --install or --uninstall is required for mutation, and only on macOS
for the current signed-in user. Binary copies are prepared before any existing
install is replaced; failures restore the prior app, CLI and LaunchAgent.
User config, archive and logs are never removed by uninstall/rollback.
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
import uuid
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


def _require_current_mac_user(home: Path) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("Per-user installation and launchctl require a real macOS machine")
    if home.resolve() != Path.home().resolve():
        raise PermissionError("Only the signed-in user's own home is supported")


def _launchctl(action: str, path: Path, *, check: bool) -> None:
    if action not in {"bootout", "bootstrap"}:
        raise ValueError("Unsupported LaunchAgent action")
    subprocess.run(
        ["launchctl", action, f"gui/{os.getuid()}", str(path)],
        check=check, capture_output=True,
    )


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _validate_artifacts(artifacts: Path) -> tuple[Path, Path]:
    app = artifacts / APP_NAME
    cli = artifacts / "pptviewer"
    if not (app / "Contents/MacOS/PowerPointArchiveAgent").is_file():
        raise FileNotFoundError("Mac app build artifact is missing")
    if not (cli / "pptviewer").is_file():
        raise FileNotFoundError("Mac console build artifact is missing")
    return app, cli


def _install_transaction(paths: dict[str, Path], artifacts: Path, scan_root: Path | None, home: Path) -> None:
    app_source, cli_source = _validate_artifacts(artifacts)
    if not paths["config"].exists() and (scan_root is None or not scan_root.is_dir()):
        raise ValueError("A local --root folder is required for a new installation")

    for name in ("app", "cli", "logs", "plist"):
        target = paths[name]
        (target if name == "logs" else target.parent).mkdir(parents=True, exist_ok=True)

    token = uuid.uuid4().hex
    staged = {
        "app": paths["app"].with_name(".pptviewer-app-stage-" + token),
        "cli": paths["cli"].with_name(".pptviewer-cli-stage-" + token),
        "plist": paths["plist"].with_name(".pptviewer-plist-stage-" + token),
    }
    backups = {
        "app": paths["app"].with_name(".pptviewer-app-backup-" + token),
        "cli": paths["cli"].with_name(".pptviewer-cli-backup-" + token),
        "plist": paths["plist"].with_name(".pptviewer-plist-backup-" + token),
    }
    touched: set[str] = set()
    old_plist = paths["plist"].is_file()
    stopped_old_agent = False
    installed = False
    try:
        # Any copy/write failure here leaves the installed app fully untouched.
        shutil.copytree(app_source, staged["app"], symlinks=True)
        shutil.copytree(cli_source, staged["cli"], symlinks=True)
        staged["plist"].write_bytes(plistlib.dumps(create_plist(home)))

        # Bootstrap the config with the staged new CLI (not the old executable).
        # Preserve user state even if later launchctl operations fail.
        if not paths["config"].exists():
            assert scan_root is not None
            subprocess.run(
                [str(staged["cli"] / "pptviewer"), "init-config",
                 "--root", str(scan_root), "--include-pdf"],
                check=True, capture_output=True,
            )

        if old_plist:
            _launchctl("bootout", paths["plist"], check=False)
            stopped_old_agent = True

        for name in ("app", "cli", "plist"):
            dest = paths[name]
            if dest.exists():
                os.replace(dest, backups[name])
            touched.add(name)
            os.replace(staged[name], dest)

        _launchctl("bootstrap", paths["plist"], check=True)
        installed = True
    except Exception:
        # Reverse all partially promoted paths. Existing config/log/archive
        # remain unchanged; a newly created config is deliberately preserved.
        for name in ("plist", "cli", "app"):
            if name not in touched:
                continue
            _remove(paths[name])
            if backups[name].exists():
                os.replace(backups[name], paths[name])
        if old_plist and stopped_old_agent and paths["plist"].is_file():
            try:
                _launchctl("bootstrap", paths["plist"], check=True)
            except Exception:
                # Native acceptance must verify launchctl restoration behavior.
                pass
        raise
    finally:
        for target in staged.values():
            _remove(target)
        if installed:
            for backup in backups.values():
                # Only successful installs discard previous binary backups.
                _remove(backup)


def install(home: Path, artifacts: Path, scan_root: Path | None) -> None:
    _require_current_mac_user(home)
    paths = mac_paths(home)
    _install_transaction(paths, artifacts, scan_root, home)
    print("Installed per-user macOS agent. Native Automation consent may be requested.")


def _uninstall_transaction(paths: dict[str, Path]) -> None:
    plist = paths["plist"]
    if plist.is_file():
        try:
            data = plistlib.loads(plist.read_bytes())
        except (ValueError, plistlib.InvalidFileException) as exc:
            raise RuntimeError("Refusing to uninstall unexpected/invalid LaunchAgent plist") from exc
        if data.get("Label") != LAUNCH_LABEL:
            raise RuntimeError("Refusing to uninstall unrelated LaunchAgent")
        _launchctl("bootout", plist, check=False)

    # Only remove the app, support CLI bundle and this label's plist.
    # Data and logs remain in the user's Application Support and Logs folders.
    for key in ("plist", "cli", "app"):
        _remove(paths[key])


def uninstall(home: Path) -> None:
    _require_current_mac_user(home)
    _uninstall_transaction(mac_paths(home))
    print("Removed agent, CLI and LaunchAgent. User config, archive and logs were preserved.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=Path("dist"))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--root", type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--plan", action="store_true", help="Show install plan (default)")
    group.add_argument("--install", action="store_true", help="Install/upgrade for this Mac user")
    group.add_argument("--uninstall", action="store_true", help="Remove app and LaunchAgent; retain all data")
    args = parser.parse_args(argv)
    if args.install:
        install(args.home, args.artifacts, args.root)
    elif args.uninstall:
        uninstall(args.home)
    else:
        print(json.dumps(plan(args.home, args.artifacts, args.root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
