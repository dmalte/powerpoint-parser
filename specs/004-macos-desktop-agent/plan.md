# macOS Architecture and Implementation Plan

- Feature: specs/004-macos-desktop-agent
- Milestone: M008
- Requirements: REQ-MAC-001

## Data Flow

- Windows PPTX → current COM Renderer.export_slides → images; python-pptx → text/notes; shared SQLite/JSON.
- Mac PPTX → PowerPoint AppleScript saved PDF → PyMuPDF → the same final images; python-pptx → original text/notes; shared SQLite/JSON.
- Optional Mac fallback: user explicitly configures LibreOffice headless PDF conversion, same rasterizer.
- Original PDFs use existing PyMuPDF handler unchanged.

## Implementation

- New renderer implements start/stop/export_slides. Factory selects COM on Windows, PowerPoint/AppleScript on Mac, optional LibreOffice on non-Windows.
- osascript uses argv for untrusted paths, never script string interpolation; timeout and validated page count, subprocess logs paths only locally. Automate only a temporary copy of the PPTX to avoid closing a user's open original. Do not quit user's PowerPoint process or return raw stderr through HTTP status.
- Rasterize in private temporary output; promote successful JPEGs into deck assets. No intermediate PDF persists.
- Persist macOS file paths under Application Support, and use macOS open/open -R for Finder actions.
- Build optional per-user LaunchAgent and PyInstaller Mac packaging scaffold. No new production Python dependencies. Tests mock osascript and LibreOffice; no false claims about real Mac compilation.
- Renderer image files remain nontransactional with SQLite/JSON; image versioning is separate.

## Limits

- PowerPoint GUI supports JPEG export, but unattended AppleScript JPEG export not proven; temp PDF is pragmatic first automation backend.
- Mac-only PowerPoint AppleScript, Automation consent, native package build, login launch, and fidelity need validation on a real Mac. No macOS launch privileges assumed on Pi.

## M008a–d Pi implementation approach (2026-11-12)

- Introduce a shared asset_generations module for PPTX/PDF processing: stage to a unique temporary deck directory; on success validate all images, atomically rename into an immutable generation subfolder; use its path in Slide.thumb_path/preview_path. Perform SQLite upsert afterward; delete newly promoted generation on SQL failure. Preserve previous generations while the static viewer/active sessions may reference them, including after deletions. Explicit cleanup is deferred.
- Replace macOS installer in-place copytree with a backed-up, staged per-user deployment (retaining bundle symlinks); launchctl operations are isolated for failure injection, rollback, and data-preserving uninstall. Native acceptance pending.
- Add scripts/diagnose_macos.py using shared configuration for path-free local readiness reporting without triggering Automation or uploading data.
- Add scripts/build_macos_fixtures.py (python-pptx/Pillow) and scripts/compare_slide_images.py (Pillow) with local-only HTML/JSON outputs, deterministic test fixtures and reference tests.
- No new production dependencies, no Windows renderer API change, no schema migration. End-to-end native Mac automation/signature/permissions still pending.

## Mac1 native execution findings (2026-11-12)

- Fetch directly from the Pi development worktree and fast-forward the clean Mac branch; do not push origin/main.
- An isolated macOS Python 3.12 .venv supports all portable tests. PyInstaller produces arm64 CLI and app bundles with the shared frontend resources; local ad hoc codesign verify passes.
- A bundled-CLI PDF-only test produced its index/thumbnail/HTML. Packaged .app started a localhost server and accepted a shutdown in a sandboxed HOME. Startup was approximately 35 seconds in the first run and should be timed again.
- Mac PowerPoint 16.115 accepts AppleScript version queries and document opening, but save as PDF yields -9074. HFS target conversion, delayed activate, and PowerPoint-container staging did not resolve it. Direct JPG save is declared in PowerPoint.sdef but the trial timed out.
- Re-run the new opt-in smoke_macos_powerpoint.py command from an unlocked user session, inspect required Automation/File Access dialogs and a manual File > Export > PDF test, then revise renderer only after identifying the native cause. Keep M008 and native installer acceptance open.

## M008e implementation

- After copying the PPTX to the renderer's unique temporary directory, use the existing python-pptx dependency to clear OOXML hidden-slide show=0/show=false flags in that copy only. Save only if flags actually changed. Both PowerPoint/AppleScript and opt-in LibreOffice then render the full expected slide sequence; original metadata is extracted from the untouched source.
- No SQLite change, configuration option or Windows COM behavior change. The temporary modified PPTX and PDF are deleted when the conversion context exits.
- Validate Pi tests first, then retest using the signed-in Mac Terminal since system-daemon MCP AppleScript conversion is not yet reliable.
