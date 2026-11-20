# macOS Desktop Agent — Source Preparation

This directory contains a **Mac-only build/install scaffold** prepared and statically tested on Raspberry Pi. It has not yet been compiled or run on a Mac.

## Parallel source development and packaged agent (M014)

The installed Mac application remains **`~/Applications/PowerPointArchiveAgent.app`** using port **8080**, the config/index under **`~/Library/Application Support/PowerPointVisualArchive/`**, its logs under **`~/Library/Logs/PowerPointVisualArchive/`**, and the existing LaunchAgent label `uk.pptvisualarchive.agent`.

The source dev agent uses an independent port **8081** and its own `repository/.runtime/dev-agent/config.yaml`, `archive/`, `logs/` and synthetic fixture library. It never replaces the packaged app or migrates/copies its archive. With the Mac signed in, use `packaging/macos/Start-Dev.command` to initialize and run it, `Stop-Dev.command` to stop it, and `Status-Dev.command` for diagnostics. A separate optional *source-mode* per-user LaunchAgent has label `uk.pptvisualarchive.dev`:

```bash
python packaging/macos/manage_dev_launchagent.py --plan
python packaging/macos/manage_dev_launchagent.py --install   # only in verified signed-in GUI session
python packaging/macos/manage_dev_launchagent.py --uninstall # preserves dev YAML/index
```

The dev LaunchAgent has `KeepAlive=false`, uses the source `.venv` interpreter, runs on login and leaves the installed label/config untouched. It must be installed on a **live Mac user GUI session**, not prepared on a Pi and treated as deployed. Do not run both agents against the same Microsoft PowerPoint automation session at the same time without pausing the packaged scanner. The initial dev fixture only indexes PDF and Markdown, avoiding Office permission prompts.

As of M014 initial preparation, **Mac1 is offline**; the scripts and LaunchAgent plan are committed but no Mac plist/source dev runtime is installed or validated. Return to this acceptance step after Mac1 is reachable.

## Runtime outputs

The shared viewer always stores:

- PPTX originals unchanged, with searchable titles, body text and notes from python-pptx.
- JPEG (or configured PNG) thumbnail and preview images per slide, with the same filenames and SQLite/JSON fields as Windows.
- No converted PDFs in the long-lived archive.

Windows continues to use PowerPoint COM to export images directly.

On macOS, native PowerPoint's *GUI* exposes JPEG/PNG export, but unattended AppleScript access to that command has not been verified. The first programmatic backend uses PowerPoint's AppleScript save-as-PDF capability, rasterizes that temporary PDF with PyMuPDF and deletes it after successful image conversion. It makes and opens a private copy before conversion so it cannot close or overwrite a user-owned original already open in PowerPoint; it does not quit the PowerPoint application.

The optional backend uses LibreOffice headless PPTX-to-temporary-PDF with a unique per-conversion profile. It does **not** activate automatically if Mac PowerPoint fails: explicitly choose render.mac_pptx_backend: libreoffice and accept possible fidelity differences.

## Prepare on Raspberry Pi (safe, no Mac modified)

    python scripts/preflight_macos_package.py --json .runtime/macos-preflight.json
    python -m pytest tests/test_macos_renderer.py tests/test_macos_packaging.py -q

The preflight checks source files, PyInstaller definition, app/CLI setup, LaunchAgent installer, renderer selection and native command source. A pass does not validate real PowerPoint or a working macOS application.

A *plan-only* deployment preview:

    python packaging/macos/install_agent.py --plan

## Build on a real Mac (not performed yet)

On a Mac with Python 3.10+ and PowerPoint for Mac installed:

    ./packaging/macos/build.sh

This prepares dist/PowerPointArchiveAgent.app and dist/pptviewer/ using PyInstaller. It neither installs nor registers auto-start. No Python installation is required for the eventual installed bundle, but Python and PyInstaller are required on the build host.

For source-mode experimentation without a bundle, the existing CLI is usable:

    python -m pip install -e ".[dev]"
    pptviewer init-config --root "/path/to/presentations" --include-pdf
    pptviewer agent

## Per-user installation on Mac (not performed yet)

A dry run can show paths and required artifacts without modifying anything:

    python packaging/macos/install_agent.py --plan --artifacts dist

An explicit --install --root /path/to/presentations on a signed-in Mac copies the app to ~/Applications, the console CLI under ~/Library/Application Support/PowerPointVisualArchive/bin, and creates a LaunchAgent in ~/Library/LaunchAgents. The installer bootstraps the current user session via launchctl; it does not use sudo, a root daemon or a system-wide Service.

The initial config under ~/Library/Application Support/PowerPointVisualArchive/config.yaml is created only when absent; upgrades preserve it. Archive files live under the same Application Support directory, and logs under ~/Library/Logs/PowerPointVisualArchive.

The current script is a **developer-oriented install scaffold**, not a signed/notarized distribution package or a tested upgrade/uninstaller.

## Pi-prepared lifecycle, readiness and acceptance tools (M008a–d)

The app and CLI are now staged before replacing the prior installed versions. If LaunchAgent bootstrap fails, the prior app, CLI and plist are restored. Previous configuration, archive database and logs are retained during upgrade and uninstall. The installer accepts --install and --uninstall only on a signed-in Mac; --plan is safe on Pi. Upgrading an existing config no longer requires --root.

    python packaging/macos/install_agent.py --plan
    python packaging/macos/install_agent.py --install --artifacts dist --root /path/to/presentations
    python packaging/macos/install_agent.py --uninstall

**Native installation/rollback/uninstall behavior has not been run on macOS.** Installer failure paths are mocked and validated on Pi. A failure to stop an already-running LaunchAgent may require native troubleshooting; this code is not a signed/notarized consumer installer.

A nonexecuting, path-free readiness report:

    python scripts/diagnose_macos.py --json .runtime/macos-readiness.json

Reference fixture generation and visual comparison (after actual Mac and Windows rendering):

    python scripts/build_macos_fixtures.py --output .runtime/mac-reference
    python scripts/compare_slide_images.py --reference /path/to/windows/deck-version --candidate /path/to/mac/deck-version --kind preview --output .runtime/image-comparison

Current PDF/PPTX image generations are immutable: old image paths are retained for still-open viewer sessions. This can grow disk usage until explicit safe garbage collection is implemented. The original-text and temporary-PDF behavior is unchanged.

## Current native Mac1 evidence (2026-11-12)

- Mac checkout: a standard per-user development workspace at a31f08b before the native-testing checkpoint; clean checkout prior to local build.
- Project environment: isolated .venv, Python 3.12; full 132-test portable suite passed.
- PyInstaller build: completed on Apple Silicon (arm64). Native preflight passed 17/17 checks, both CLI and application bundle exist.
- Bundled CLI: --help, PDF scan and HTML viewer build passed. Native application started its localhost server, served status/viewer, and accepted shutdown while HOME pointed to an isolated test directory.
- Codesign: strict verification passed with ad hoc signature; no Developer ID team or notarization, not ready for distribution.
- PowerPoint 16.115: AppleScript get version works; PPTX-to-PDF save returns -9074 after trying normal, HFS-style, activated/delayed and Office-container paths. The installed dictionary enumerates save as JPG, but a trial did not return images before timeout.
- No permanent ~/Applications installation or LaunchAgent registration was performed. User data and installed PowerPoint were not modified.

To reproduce the current native failure while signed in and unlocked:

    .venv/bin/python scripts/smoke_macos_powerpoint.py --backend powerpoint --timeout 25

Report: .runtime/mac-native/pptx-smoke/result.json. A -9074 response is an unresolved native PowerPoint automation/environment failure, not a successful rendering result. Inspect pending Automation/File Access prompts and test manual File > Export > PDF in the PowerPoint GUI. Do not silently switch to LibreOffice.

## Hidden-slide completeness (M008e)

A native six-slide reference presentation exported **five** PDF pages because PowerPoint omitted its intentionally hidden final slide. The previous smoke test reported a failure even though its shell command exited successfully. The PDF-backed renderer now uses python-pptx to clear hidden-slide flags **only in the temporary PPTX copy** before AppleScript/LibreOffice conversion, maintaining slide numbering and avoiding changes to the user's PPTX. Pi regressions cover hidden slides in the middle and end, notes, and original-byte preservation. Mac1 interactive acceptance now passes after synchronizing commit 0329508: 6/6 slides, six thumbnails and six previews, all expected sizes; six original titles/notes and the unchanged hidden-slide flag and source checksum were verified. Real LaunchAgent and Windows/Mac visual comparisons remain pending.

The two-slide native PowerPoint test succeeded through the logged-in Terminal (~28 seconds), whereas the system MCP-daemon execution timed out or returned -9074. Rendering must run in the signed-in graphical session; the permanent user LaunchAgent remains uninstalled.

## PowerPoint sandbox prompts and safe restart (M008f)

PowerPoint for Mac runs sandboxed. During a large library scan, passing a unique temporary PPTX and PDF located under the archive's asset directory can trigger a file-access grant for *every deck*. The renderer now uses a per-conversion temporary subdirectory inside the **Microsoft PowerPoint container's Documents folder** for those two intermediate files, with automatic cleanup. Only generated JPEG thumbnails/previews remain in the local archive; originals and speaker notes are never modified.

The archive app is a different code-signing identity from Microsoft PowerPoint. On modern macOS, it may need one permission grant to enter PowerPoint's container. If denied, processing reports a workspace-access error and preserves previous images/SQLite rows. The user should grant access only if they recognize the PowerPoint Archive app. Do not edit sandbox bookmarks or broaden file permissions.

Mac1's 3,952-file scan was paused after 9 files and four reported errors; the per-user LaunchAgent was booted out and its original plist held under user Application Support to prevent relaunch on next login. Do not restart the full library until a separate small fixture library succeeds without one prompt per presentation. An updated native app was built and passed package checks, but its isolated gui/501 background LaunchAgent failed both synthetic PPTX conversions with PowerPoint -9074, so this staging fix is not yet accepted. That test LaunchAgent was removed; the production agent and its startup plist remain held. A user Terminal smoke with the new staging is needed before another background-mode approach is selected.

### M008f native retry result

The next signed-in Terminal smoke passed the staged two-slide PowerPoint export. A fresh isolated user LaunchAgent subsequently processed both reference PPTX decks (8 slides) and four additional copied synthetic PPTXs (16 slides) with 0 processing errors; the local viewer indexed six decks / 24 slides. No PowerPoint temporary staging directories remained. The earlier -9074 failures were intermittent. The isolated test LaunchAgent was removed and the production auto-start remains disabled. **Ask the user if permission dialogs appeared during the successful test**; API success alone does not establish that the repeated permission prompts are gone. Do not restart the production library without confirmation.

## Pause/resume and saved partial archives (M008g)

The agent exposes **Pause Scan & Save** / **Resume Scan** controls on both http://127.0.0.1:8080/ and /settings.html. Pausing is cooperative after the current file and publishes the committed SQLite state as a browsable HTML/JSON archive; it doesn't kill PowerPoint or delete unvisited entries. Existing images and the old viewer remain available if publishing fails.

The user's paused choice is durably saved as processing.scan_paused: true in per-user YAML and persists across login/restarts. Scheduled scans stay inactive until an explicit Resume action; resume is incremental, rediscovers sources and skips already indexed unchanged documents. Partial scans defer deletion processing until a later complete pass. Loopback endpoints: POST /api/pause, POST /api/resume, GET /api/status (includes scan_paused and snapshot_pending).

Mac1 now runs the upgraded arm64 app with the new controls. Its existing YAML and SQLite were backed up and preserved, with 2,959 decks / 15,809 slides published; production remains paused. A separate user agent validated Resume, Pause and restart. Other Mac installations still need the native rebuild/upgrade. Do not replace or delete the user's existing SQLite archive/configuration; the staged installer preserves both. With a large archive, deploy in the paused state and verify partial viewer publication before the user explicitly resumes.

## Required native Mac acceptance

- Verify the exact AppleScript syntax using the installed Microsoft PowerPoint version and an actual multi-slide PPTX.
- Grant macOS Automation consent for the final bundled agent to control Microsoft PowerPoint; verify that headless LaunchAgent execution is permitted.
- Confirm that one-page-per-slide PDF rendering preserves the visual layout and page count, including hidden slides.
- Compare output JPEG/PNG quality and dimensions with the Windows COM output. Check font substitution and embedded graphics.
- Test LibreOffice headless only if explicitly enabled, with a representative complex deck.
- Build PyInstaller app and CLI on macOS, verify NSAppleEventsUsageDescription, signing/notarization/Gatekeeper constraints, launch-on-login, active-user behavior, Finder open/reveal, and restart/error recovery.
- Test under a new user account, including missing-drive scenarios and performance on a large library.

Do **not** mark M008 accepted before native Mac checks pass.

## Cumulative 0.1.4 distribution image (M017)

After a native `./packaging/macos/build.sh` succeeds, run
`./packaging/macos/build_release.sh <verified-source-SHA>` on the Mac. It
compiles `install_agent.py` as a standalone executable, prepares a disk image
with the self-contained app+CLI, `Install.command`, `Uninstall.command`, and
`BUILD_INFO.txt`, validates the installer `--plan` on its staged artifacts,
then checks DMG integrity and the app's ad-hoc signature. The output is
`dist/release/PowerPointVisualArchive-macOS-<arch>-0.1.4-unnotarized.dmg`.
This packaging step never changes the installed user agent. Installation is
explicit and uses the already-tested per-user transactional lifecycle.
Code signing here is **ad hoc**, not Apple Developer ID; the image is **not
notarized**. Browser download Gatekeeper checks and Office Automation consent
remain user/production acceptance gates. Never claim a notarized installer.

A public source PR should not include the binary; once acceptance passes, upload
the checksum-identified DMG as a GitHub Release asset instead.
