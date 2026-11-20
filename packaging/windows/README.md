# Windows Packaging

This directory contains the Phase 1 Windows packaging scaffold for the per-user PowerPoint Visual Archive agent. It intentionally uses an interactive user-session agent, not a Windows Service, because PPTX rendering relies on Microsoft PowerPoint COM automation.

## Independent development instance (no installer required)

The signed-in user can run the **editable Python developer agent** directly from the Git checkout. It is **not** a second installation of the Inno Setup application, and it never shares the installed archive:

| | Source development | Installed package |
|---|---|---|
| Entry point | `packaging/windows/Start-Dev.cmd` | `%LOCALAPPDATA%/Programs/PowerPoint Visual Archive/PowerPointArchiveAgent.exe` |
| Port | `127.0.0.1:8081` | `127.0.0.1:8080` |
| Config | `.runtime/dev-agent/config.yaml` | `%LOCALAPPDATA%/PowerPointVisualArchive/config.yaml` |
| Index/preview output | `.runtime/dev-agent/archive/` | `%LOCALAPPDATA%/PowerPointVisualArchive/archive/` |
| Agent log | `.runtime/dev-agent/logs/agent.log` | `%LOCALAPPDATA%/PowerPointVisualArchive/logs/agent.log` |

After a one-time editable install in the project's `.venv`, open **Start-Dev.cmd** while logged into the Windows desktop. **Stop-Dev.cmd** requests a graceful shutdown but refuses to stop an unknown listener on port 8081. **Status-Dev.cmd** reports connectivity, config and instance ownership. Equivalent CLI commands are `python scripts/dev_agent.py init/run/stop/doctor`. Dev initialization never overwrites its YAML and only creates small synthetic PDF and Markdown fixtures; it does not scan a user's real presentation library by default. A new source commit needs a dev-agent restart but **not** a new installer.

To launch source development automatically in the **same signed-in Windows user session**, use the separate Task Scheduler helper (requires the existing developer `.venv` and a logged-in interactive user):

```powershell
python packaging/windows/manage_dev_task.py --plan
python packaging/windows/manage_dev_task.py --install
python packaging/windows/manage_dev_task.py --start
python packaging/windows/manage_dev_task.py --status
python packaging/windows/manage_dev_task.py --uninstall
```

This creates only a **`PowerPointVisualArchive-Dev-Agent`** user-token task with logon startup, ignore-new-duplicate policy, and `pythonw.exe` running `scripts/dev_agent.py run`. It neither replaces nor modifies the packaged application's user-logon Startup shortcut, binaries or archive. Removing the dev scheduler task preserves its independent `.runtime/dev-agent` data. Before installation, verify the Scheduler helper's exact expected executable and the active desktop user; the helper refuses foreign tasks and never uses a system account/service token for PowerPoint.

The `windows` Pi-federation shell may run as the same user in Windows Session 0. It may initialize/test dev files but **must not** start PowerPoint COM or the source GUI agent there. The installed agent remains in the signed-in user's desktop session. Both agents can serve different local ports concurrently; avoid simultaneous Office COM conversions by pausing the packaged scan before developing PPTX rendering. An interactive logon shortcut or task must be tied to the correct user and verified before enabling autostart.

## Prerequisites for building

- Windows 10/11 x64
- Python 3.10+ for the build workstation
- Microsoft PowerPoint for PPTX smoke validation
- Inno Setup 6 or 7 (`ISCC.exe` discovered on `PATH` or in the standard Windows installation directories)

The installed end-user application is self-contained and does not require Python or Git.

## Build

From PowerShell at the repository root:

```powershell
.\packaging\windows\build.ps1 -Version 0.1.4
```

The script prepares the project virtual environment, installs the `packaging` optional dependency, builds two PyInstaller executables, and compiles the Inno Setup installer. Expected outputs:

```text
dist\pptviewer.exe
dist\PowerPointArchiveAgent.exe
dist\installer\PowerPointVisualArchiveSetup-0.1.4.exe
```

`pptviewer.exe` is the console/support CLI. `PowerPointArchiveAgent.exe` is windowless and starts the `agent` command directly. Both bundles include the `web/` templates and static assets used to generate the viewer.

## Installer behavior

The installer runs per user with `PrivilegesRequired=lowest` and installs under the current user's local application-data programs directory. On a first install it asks for a presentation folder and runs `pptviewer init-config` to create the per-user configuration and archive directory. Existing `%LOCALAPPDATA%\PowerPointVisualArchive\config.yaml` is preserved during upgrades.

The installer creates a current-user Startup shortcut for `PowerPointArchiveAgent.exe`, so the archive agent launches in the signed-in user's interactive Windows session at logon.

## Cross-platform packaging preflight (M004a)

Run on the Raspberry Pi, Mac or Windows before building:

    python scripts/preflight_windows_package.py --json .runtime/packaging/preflight.json

This stdlib-only command checks source assets, PyInstaller entries, conditional pywin32, the Inno Setup per-user/startup/config-preservation definitions, version consistency, and PowerShell native-command error handling. It reports a warning when Windows-built artifacts are not supplied. The build helper now runs this preflight before dependency installation and checks PE signatures after the build:

    python scripts/preflight_windows_package.py --artifacts dist --version 0.1.4

Use --skip-installer when only the two EXEs were built. The version must match the project's declared version; update pyproject, build default and installer default together when preparing a new release. The optional PE signature check does not prove executable behavior, security signature, installer correctness, or PowerPoint COM support.

**Passing preflight is not Windows acceptance.** The real build, install, upgrade, logon, COM rendering, tray controls and uninstall checks below are still required.

## M004b Windows upgrade preparation (2026-11-17)

A previously installed v0.1.0 agent can be running from the signed-in user's `%LOCALAPPDATA%/Programs/PowerPoint Visual Archive`, even when the local source checkout is new. **Do not start two agents on the same archive or install over a running agent without a consistent SQLite/YAML backup.** The new build candidate is v0.1.1 and preserves the same Inno AppId/configuration/data path.

The federation-based remote shell runs in Windows Session 0 and does **not** inherit the signed-in user's profile. It can perform source/preflight and native build checks, but PowerPoint COM, Settings/tray, installer UI and initial user-state changes must be validated in the actual interactive user session (Session 1 or an RDP user session). The tray helper skips Session 0, and the data-path helper refuses missing Windows `LOCALAPPDATA`. No Session 0 smoke test is evidence that the installed GUI works.

Before upgrading an existing installation, back up `%LOCALAPPDATA%/PowerPointVisualArchive/config.yaml` and its SQLite index consistently (`sqlite3.backup`), verify SQLite `PRAGMA quick_check`, save the existing installed EXEs, and stop the agent gracefully. Then install the new version for the **same** logged-in user. First validation should use an isolated small test folder with one PPTX and one PDF; do not remove the historical archive. Verify `http://127.0.0.1:8080/` and `/settings.html`, Pause/Resume, COM images, restart/logon, config/db persistence and uninstall/rollback.

## Current Windows build result — 0.1.1 (2026-11-17)

A native Windows x64 build completed from private source commit `e58761d` with PyInstaller 6.22.2, Python 3.14.3 and Inno Setup 7. Both executables and the Inno installer compiled successfully, and the source + native PE artifact preflight returned success. The unsigned `PowerPointVisualArchiveSetup-0.1.1.exe` is approximately **90.5 MiB**, SHA-256 `7a26b8e3d1e127a2cf3ac048769d3bfcf43ba4d70bd813d1eaf222b0d7e97159`, located in the ignored Windows development staging under `.runtime/m004b-release-e58761d/dist/installer/`. The original August v0.1.0 installer and the installed application were preserved.

**This is a build candidate, not a validated upgrade.** The Windows federation route later became unavailable. An isolated packaged CLI PDF/Markdown smoke and interactive-session Windows PowerPoint/Settings/tray/logon/upgrade smoke remain pending. The installed application in Session 1 must not be replaced by running the installer as the Session 0 federation account. Back up the production archive/config, then validate under the original user's interactive session; see the smoke steps below.

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

## M004d — Real windowless EXE isolated acceptance (0.1.2 candidate)

The source `PowerPointArchiveAgent.exe` launcher now forwards **optional** `agent` CLI flags, while normal no-argument installed startup still uses port 8080 and the existing user YAML. For a safe GUI/console=False smoke test, run the Windows native bundle **in Session 1** with explicit `--config <isolated test YAML> --port 8082 --log-dir <isolated test logs> --scan-interval 0`. Use only synthetic PDF/Markdown fixtures, not Office COM or installed data. Validate `/api/status`, `/`, `/settings.html`, Pause/Resume, SQLite integrity, owned shutdown and repeated startup. The older 0.1.1 bundle predates the windowless HTTP bug fix and must not replace the packaged 0.1.0 app. Rebuild from 0.1.2 private source and pass GUI tests before considering a production upgrade.

### Final 0.1.2 isolated Windows GUI acceptance — 2026-11-17

An independently compiled Windows x64 0.1.2 **unsigned candidate** from committed private source `68eb190` is located in the Windows checkout under `.runtime/m004d-final-68eb190/dist/installer/PowerPointVisualArchiveSetup-0.1.2.exe` (90.5 MiB, SHA-256 `d264772669aa93bc5775d0675f70f5af31983658f164c5af303ebc763eeef84b`). PyInstaller, Inno Setup 7 and the native PE artifact preflight all passed. This does not constitute a signed installer release.

A disposable Task Scheduler interactive-token job ran the actual frozen `PowerPointArchiveAgent.exe` as the signed-in Windows user on **port 8082**, with a separate synthetic PDF/Markdown config/SQLite/archive/logs and `--scan-interval 0`. All of `/`, `/settings.html`, `/api/status`, `/data/export.json` and `/api/performance` returned HTTP 200. Two documents/two page records/four previews were indexed; SQLite quick_check=ok and the dedicated performance.jsonl contained two events. Pause/Resume returned HTTP 202 and state persisted; graceful shutdown was accepted and port 8082 freed. The temporary job and previous harmless probe job were removed; Windows **source dev 8081** remains running under its own user-logon task and **installed v0.1.0 8080** remains unchanged. The installed YAML still matches its backup byte-for-byte; live and backup SQLite quick_check=ok, 5,322 documents.

The current 0.1.2 binary is an **accepted isolated GUI test candidate only**, **not installed over production**. The real Windows PowerPoint COM test, signed-in upgrade/rollback/logon and uninstall acceptance, as well as code signing, are still pending M004. Keep the existing verified user data and backup intact.

## M004e — 0.1.3 Upgrade File-Lock Handling

The first interactive v0.1.2 upgrade attempt failed at the Windows installed `PowerPointArchiveAgent.exe` with `DeleteFile failed; code 5; Access is denied`. An independent probe proved the existing windowless v0.1.0 agent remained running in Session 1 and the backup SQLite was intact. **Do not choose `Skip this file`**: that would produce a mixed-version installation. Cancel the 0.1.2 wizard before running another installer.

Starting with the **new 0.1.3 build**, Inno's Restart Manager forcibly closes an unresponsive holder of the two bundled EXE file resources if normal closure fails (`CloseApplications=force`, `CloseApplicationsFilter=PowerPointArchiveAgent.exe,pptviewer.exe`, `RestartApplications=no`). This does **not** stop the independent source-dev `pythonw.exe` or touch its port 8081. The installer keeps the same AppId and per-user data paths; it preserves YAML/index/images/logs and creates the user-logon Startup shortcut for the **new** binary. A force-close can interrupt an active scan; verify the user's SQLite backup and avoid an active conversion before installing. If an executable remains locked, do not skip it.

Static preflight and native compilation are required but not sufficient for accepting production upgrade. Install in the user's interactive desktop; verify the old app exited, the new 8080 agent responds, the 8081 developer viewer remains healthy, original user YAML/index is preserved with valid SQLite, and the signed-in PowerPoint COM and relogin tests pass. Only then mark M004 accepted.

### Verified 0.1.3 native installer (2026-11-19)

Native Windows x64 setup from private `04e5e3b` completed PyInstaller, Inno Setup 7 and 18/18 artifact checks successfully. Unsigned setup is 90.5 MiB with SHA-256 `5a656d871cbc6e7b09f6f19a9a5e6b61510320659e68f0e9ac9a91df729a08a9`, available under `.runtime/m004e-release-04e5e3b/dist/installer/` and as a byte-identical verified copy in `%USERPROFILE%/Downloads`.

The failed 0.1.2 installation partially updated `pptviewer.exe` but left the old locked agent. Active/backup SQLite quick_check=ok (5,322 decks), config unchanged and dev 8081 healthy. **Do not retry 0.1.2 or skip the locked EXE.** In the signed-in desktop run 0.1.3 and permit automatic closure in the Inno Preparing to Install step. Afterward verify both installed binaries match the new build, new HTTP 8080 works and dev HTTP 8081 remains unchanged. Native forced-shutdown upgrade and Office COM still require real acceptance.
