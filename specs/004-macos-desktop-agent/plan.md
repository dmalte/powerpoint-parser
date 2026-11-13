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

## M008e native result (2026-11-12)

- On Mac1 after fast-forwarding commit 0329508, the interactive user-session script rendered 6/6 slides in 15.27s with Office error null, including the hidden sixth slide. Six 320x180 JPEG thumbnails and six 1280x720 JPEG previews were verified with Pillow.
- The original PPTX SHA-256 matched the reference manifest, the sixth slide remained hidden in the original, and all six titles and speaker notes matched. The archive still indexes metadata from the unmodified original.
- Mac packaged LaunchAgent Automation/permissions, user logon, upgrade/uninstall and pixel-level comparison with Windows PowerPoint output remain open. System-daemon PowerPoint export is unreliable and not a supported renderer execution context.

## M008f — Microsoft PowerPoint sandbox staging (2026-11-12)

- MacPowerPointRenderer should stage only the temporary input PPTX and destination PDF within ~/Library/Containers/com.microsoft.Powerpoint/Data/Documents/PowerPointVisualArchive. Preserve a unique temporary working subdirectory for each conversion and remove all temporary bytes when the conversion completes. Keep the image rasterizer's staging/output and final index under the archive root; no private originals are moved or modified.
- Make the Mac PowerPoint container selection an overridable method/test seam (not a user-configurable arbitrary path), so tests use local temporary directories and never write into a real app sandbox. The optional LibreOffice backend keeps its existing private profile/output behavior.
- macOS 14+ may require one permission grant for a separately signed agent to access another app's container. Refuse or report access denial clearly; do not add Full Disk Access, scripts that forge sandbox bookmarks, or permission-bypassing workarounds.
- Before production scan, validate two reference PPTX exports, the hidden-slide fixture, missing-permission errors, and cleanup. Keep the LaunchAgent booted out and disabled during validation to avoid thousands of dialogs.

## M008f native isolation result (Mac1, 2026-11-12)

- Fast-forwarded clean Mac1 to a159312 and rebuilt Apple Silicon .app/CLI (PyInstaller 6.22.3); native package preflight 17/17 and ad hoc strict codesign verification passed.
- A dedicated, separate gui/501 LaunchAgent with an isolated working directory/config/archive scanned two copied synthetic PPTXs (simple and six-slide reference). No real-library files were scanned. The updated renderer used PowerPoint's container for temporary PPTX/PDF.
- Both conversions failed with Microsoft PowerPoint -9074, zero slides indexed; /api/status reported 2 processing errors. Thus the new staging is NOT accepted as a fix for unattended native rendering and the presence/absence of repeated prompts could not be established.
- The isolated test LaunchAgent was booted out and its test plist removed. User production LaunchAgent remains booted out with its original plist safely held under Application Support, preventing the 3,952-file prompt storm at login. User's archive/config/logs remain intact.
- Next isolate native user-session versus background-process automation identity: run the existing two-slide smoke from signed-in Terminal with the updated staging to check whether it works without per-file prompts. If Terminal works and background launch still fails, qualify a LaunchServices-started application or a dedicated user-session automation helper; do not resume the large library until a test batch has zero errors and no repeated prompts.

## M008f retry after initial -9074 failure (Mac1, 2026-11-12)

- The signed-in Mac Terminal retried the same new-staging two-slide smoke: 2/2 slides, 4 JPEGs, 0.699 seconds, no Office error; the immediately preceding Terminal run had failed with -9074. This is evidence of intermittent rather than permanent failure.
- Rebuilt Mac app from a159312 was retried in a **fresh isolated gui/501 LaunchAgent** using only two synthetic fixtures: both processed successfully, eight slides and zero errors. Then four additional uniquely named copies of those fixtures were scanned incrementally: 4 new processed OK, 2 unchanged, 0 errors. Final isolated archive: 6 decks / 24 slides, published viewer, no leftover PowerPoint temp-conversion dirs.
- The test LaunchAgent was booted out and its plist removed; the original production 3,952-file agent remains disabled with its plist held. Test configurations/archives are isolated; production user settings and archive unchanged.
- Success does **not** prove no macOS file permission dialogs appeared. The operator must confirm whether the six-deck batch caused any prompts. Before declaring resolution, require a bounded real-library staged scan with guardrails, and do not auto-resume the full library.

## M008g — Cooperative pause/resume implementation

- Pipeline.run_scan gets optional callable cancellation predicate, checked before each PPTX/PDF file and after discovery. On cancellation, preserve any committed successful deck updates and return a partial summary including processed/remaining counts; defer deletion inference until a full scan has actually processed its queue. No DB migration needed.
- AgentRuntime owns one pause Event shared with run_scan, using the existing refresh lock to serialize scans, pause checkpoint publication and resume. Pause is persisted as processing.scan_paused in config.yaml before being acknowledged. The currently active scan finishes its current file and then the regular refresh_archive path builds the viewer from SQLite; when idle, pausing triggers a publish-only snapshot worker.
- On agent startup with persisted scan_paused=true, start HTTP serving without a scan and publish a partial viewer if stale/missing. Prevent scheduled/manual scans while paused; Resume atomically clears the paused setting then starts incremental scan; status exposes pause flag and pausing/publishing/paused states.
- Add POST /api/pause and POST /api/resume to loopback server and dynamic controls on viewer top bar and Settings. UI should disable ambiguous actions while a transition is in progress and continue to display the paused partial archive.
- Test with synthetic PDFs/slow mocked conversion for stop-after-current, preserved old decks/deletion safety, incremental resume, fresh HTTP status and partially published JSON/images, queued/scheduler interleavings, persistence across restart and build failure resilience.
- Native Mac rollout: stop old installed agent without deleting archive/config, publish existing SQLite as a first checkpoint if needed, update per-user config paused before installing the new app. Rebuild/sign Mac bundle, install with staged rollback, verify paused startup, viewer HTTP, Resume/Pause controls and a bounded synthetic batch. Do not run the complete 3,937-file scan as an unattended acceptance test.
