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
