# macOS Desktop Agent — Source Preparation

This directory contains a **Mac-only build/install scaffold** prepared and statically tested on Raspberry Pi. It has not yet been compiled or run on a Mac.

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

## Required native Mac acceptance

- Verify the exact AppleScript syntax using the installed Microsoft PowerPoint version and an actual multi-slide PPTX.
- Grant macOS Automation consent for the final bundled agent to control Microsoft PowerPoint; verify that headless LaunchAgent execution is permitted.
- Confirm that one-page-per-slide PDF rendering preserves the visual layout and page count, including hidden slides.
- Compare output JPEG/PNG quality and dimensions with the Windows COM output. Check font substitution and embedded graphics.
- Test LibreOffice headless only if explicitly enabled, with a representative complex deck.
- Build PyInstaller app and CLI on macOS, verify NSAppleEventsUsageDescription, signing/notarization/Gatekeeper constraints, launch-on-login, active-user behavior, Finder open/reveal, and restart/error recovery.
- Test under a new user account, including missing-drive scenarios and performance on a large library.

Do **not** mark M008 accepted before native Mac checks pass.
