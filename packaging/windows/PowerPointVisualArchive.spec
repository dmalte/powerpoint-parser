# PyInstaller build definition for the Windows Phase 1 distribution.

from pathlib import Path

project_root = Path(SPECPATH).parents[1]
src_root = project_root / "src"
web_root = project_root / "web"

hidden_imports = [
    "pythoncom",
    "pywintypes",
    "win32com",
    "win32com.client",
    "win32api",
    "win32gui",
    "win32timezone",
]

common = dict(
    pathex=[str(src_root)],
    binaries=[],
    datas=[(str(web_root), "web")],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

cli = Analysis([str(project_root / "packaging" / "windows" / "pptviewer_launcher.py")], **common)
cli_pyz = PYZ(cli.pure)
cli_exe = EXE(
    cli_pyz,
    cli.scripts,
    cli.binaries,
    cli.datas,
    [],
    name="pptviewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

agent = Analysis([str(project_root / "packaging" / "windows" / "agent_launcher.py")], **common)
agent_pyz = PYZ(agent.pure)
agent_exe = EXE(
    agent_pyz,
    agent.scripts,
    agent.binaries,
    agent.datas,
    [],
    name="PowerPointArchiveAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
