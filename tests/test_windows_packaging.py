"""Portable structural checks for the Windows Phase 1 packaging definitions."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WINDOWS_PACKAGING = ROOT / "packaging" / "windows"


def test_pyinstaller_bundle_includes_web_assets_and_windowless_agent():
    spec = (WINDOWS_PACKAGING / "PowerPointVisualArchive.spec").read_text(encoding="utf-8")

    assert "datas=[(str(web_root), \"web\")]" in spec
    assert 'name="pptviewer"' in spec
    assert 'name="PowerPointArchiveAgent"' in spec
    assert "console=False" in spec


def test_installer_is_per_user_preserves_config_and_registers_startup():
    installer = (WINDOWS_PACKAGING / "PowerPointVisualArchive.iss").read_text(encoding="utf-8")

    assert "PrivilegesRequired=lowest" in installer
    assert "{userstartup}\\PowerPoint Visual Archive" in installer
    assert "Check: not ConfigExists" in installer
    assert "init-config --root" in installer
    assert "PowerPointArchiveAgent.exe" in installer


def test_windowless_agent_launcher_forwards_explicit_isolated_gui_flags(monkeypatch):
    """Frozen GUI can be tested on 8082 while installed defaults stay on 8080."""
    import runpy
    import sys
    from ppt_visual_archive import cli

    calls = []
    monkeypatch.setattr(cli, "main", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(sys, "argv", ["PowerPointArchiveAgent.exe", "--port", "8082", "--config", "sandbox.yaml", "--log-dir", "sandbox-logs"])
    runpy.run_path(str(WINDOWS_PACKAGING / "agent_launcher.py"), run_name="__main__")
    assert calls[-1] == {"args": ["agent", "--port", "8082", "--config", "sandbox.yaml", "--log-dir", "sandbox-logs"]}
    monkeypatch.setattr(sys, "argv", ["PowerPointArchiveAgent.exe"])
    runpy.run_path(str(WINDOWS_PACKAGING / "agent_launcher.py"), run_name="__main__")
    assert calls[-1] == {"args": ["agent"]}


def test_installer_upgrades_terminate_only_locked_installed_executables():
    """Restart Manager must handle a stale installed GUI and preserve dev."""
    import re

    installer = (WINDOWS_PACKAGING / "PowerPointVisualArchive.iss").read_text(encoding="utf-8")
    assert re.search(r"^CloseApplications=force$", installer, re.MULTILINE)
    assert re.search(
        r"^CloseApplicationsFilter=PowerPointArchiveAgent\.exe,pptviewer\.exe$",
        installer, re.MULTILINE,
    )
    assert re.search(r"^RestartApplications=no$", installer, re.MULTILINE)
    assert "Source: \"..\\..\\dist\\PowerPointArchiveAgent.exe\"" in installer
    assert "{userstartup}\\PowerPoint Visual Archive" in installer
    assert "PrivilegesRequired=lowest" in installer
    # Production YAML and SQLite are not among installer-managed files.
    assert "Check: not ConfigExists" in installer
    assert not any(line.startswith("CloseApplicationsFilter=") and "pythonw.exe" in line for line in installer.splitlines())
