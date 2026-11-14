# PyInstaller source build for macOS, intended to be compiled on a real Mac.
# Produces a user-session .app agent and a console support CLI. macOS app
# signing, TCC Automation permissions and notarization need native acceptance.
from pathlib import Path

project_root = Path(SPECPATH).parents[1]
src_root = project_root / "src"
web_root = project_root / "web"

common = dict(
    pathex=[str(src_root)],
    binaries=[],
    datas=[(str(web_root), "web")],
    hiddenimports=["fitz", "pptx", "jinja2", "yaml", "markdown_it"],
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
    cli_pyz, cli.scripts, [], exclude_binaries=True,
    name="pptviewer", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=True,
)
cli_coll = COLLECT(cli_exe, cli.binaries, cli.datas, [], name="pptviewer")

agent = Analysis([str(project_root / "packaging" / "windows" / "agent_launcher.py")], **common)
agent_pyz = PYZ(agent.pure)
agent_exe = EXE(
    agent_pyz, agent.scripts, [], exclude_binaries=True,
    name="PowerPointArchiveAgent", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
)
agent_coll = COLLECT(
    agent_exe, agent.binaries, agent.datas, [],
    name="PowerPointArchiveAgent",
)
agent_app = BUNDLE(
    agent_coll,
    name="PowerPointArchiveAgent.app",
    bundle_identifier="uk.pptvisualarchive.agent",
    info_plist={
        "NSHighResolutionCapable": True,
        # This is a TCC explanation, not consent or an entitlement.
        "NSAppleEventsUsageDescription": (
            "This app controls Microsoft PowerPoint to render slides for a local archive."
        ),
    },
)
