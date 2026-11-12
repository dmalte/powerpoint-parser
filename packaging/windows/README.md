# Windows Packaging

This directory contains the Phase 1 Windows packaging scaffold for the per-user PowerPoint Visual Archive agent. It intentionally uses an interactive user-session agent, not a Windows Service, because PPTX rendering relies on Microsoft PowerPoint COM automation.

## Prerequisites for building

- Windows 10/11 x64
- Python 3.10+ for the build workstation
- Microsoft PowerPoint for PPTX smoke validation
- Inno Setup 6 with `ISCC.exe` available on `PATH`

The installed end-user application is self-contained and does not require Python or Git.

## Build

From PowerShell at the repository root:

```powershell
.\packaging\windows\build.ps1 -Version 0.1.0
```

The script prepares the project virtual environment, installs the `packaging` optional dependency, builds two PyInstaller executables, and compiles the Inno Setup installer. Expected outputs:

```text
dist\pptviewer.exe
dist\PowerPointArchiveAgent.exe
dist\installer\PowerPointVisualArchiveSetup-0.1.0.exe
```

`pptviewer.exe` is the console/support CLI. `PowerPointArchiveAgent.exe` is windowless and starts the `agent` command directly. Both bundles include the `web/` templates and static assets used to generate the viewer.

## Installer behavior

The installer runs per user with `PrivilegesRequired=lowest` and installs under the current user's local application-data programs directory. On a first install it asks for a presentation folder and runs `pptviewer init-config` to create the per-user configuration and archive directory. Existing `%LOCALAPPDATA%\PowerPointVisualArchive\config.yaml` is preserved during upgrades.

The installer creates a current-user Startup shortcut for `PowerPointArchiveAgent.exe`, so the archive agent launches in the signed-in user's interactive Windows session at logon.

## Cross-platform packaging preflight (M004a)

Run on the Raspberry Pi, Mac or Windows before building:

    python scripts/preflight_windows_package.py --json .runtime/packaging/preflight.json

This stdlib-only command checks source assets, PyInstaller entries, conditional pywin32, the Inno Setup per-user/startup/config-preservation definitions, version consistency, and PowerShell native-command error handling. It reports a warning when Windows-built artifacts are not supplied. The build helper now runs this preflight before dependency installation and checks PE signatures after the build:

    python scripts/preflight_windows_package.py --artifacts dist --version 0.1.0

Use --skip-installer when only the two EXEs were built. The version must match the project's declared version; update pyproject, build default and installer default together when preparing a new release. The optional PE signature check does not prove executable behavior, security signature, installer correctness, or PowerPoint COM support.

**Passing preflight is not Windows acceptance.** The real build, install, upgrade, logon, COM rendering, tray controls and uninstall checks below are still required.

## Windows smoke test

Use a clean Windows test account where Git and Python are not installed for end-user validation.

1. Build the installer on a Windows build workstation and copy only `PowerPointVisualArchiveSetup-<version>.exe` to the clean test account.
2. Install without elevation. Select a small folder containing at least one `.pptx`; include a `.pdf` when PDF behavior also needs validation.
3. Confirm `%LOCALAPPDATA%\PowerPointVisualArchive\config.yaml`, `archive\`, and `logs\agent.log` are created outside the program installation directory.
4. Confirm the initial agent run processes the selected content and that `http://127.0.0.1:8080` opens the generated viewer.
5. Open a PPTX entry from the viewer and verify PowerPoint opens it; exercise the containing-folder action as well.
6. Modify or add a presentation, then either wait for the default 30-minute refresh interval or run the support CLI with a shorter `agent --scan-interval` value for the test. Confirm the viewer updates without restarting the HTTP server.
7. Sign out and sign back in. Confirm `PowerPointArchiveAgent.exe` starts automatically for that user and the viewer remains available.
8. Re-run the installer as an upgrade. Confirm the existing configuration is preserved and the selected scan root is not replaced.
9. Uninstall. Confirm installed program files and Startup shortcut are removed; per-user archive/config data may remain for preservation and should be evaluated before release policy is finalized.

Record the Windows version, Office/PowerPoint version, installer version, and pass/fail result in `dev/HANDOFF.md`. M004 / REQ-DEPLOY-001 must not be marked implemented until this smoke test succeeds.
