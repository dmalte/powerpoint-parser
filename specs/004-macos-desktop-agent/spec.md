# macOS Desktop Agent Preparation

- Feature: specs/004-macos-desktop-agent
- Milestone: M008
- Requirements: REQ-MAC-001
- Status: active (Pi preparation; real macOS acceptance pending)

## Objective

Prepare a macOS per-user version of PowerPoint Visual Archive. Preserve the same outputs as Windows: slide images, and original-PPTX text/notes indexed in SQLite and JSON.

## Decisions

- Keep Windows COM slide-to-JPEG rendering unchanged.
- Microsoft documents manual JPEG export on Mac, but unattended AppleScript JPEG export is not verified. Do not claim it works from UI evidence alone.
- Initial automated Mac renderer: PowerPoint AppleScript opens PPTX and saves unique *temporary PDF*; PyMuPDF makes standard JPG/PNG thumbnails and previews. Temp PDF is deleted. Original text/notes remain from python-pptx.
- Explicit LibreOffice headless conversion is optional, not a silent fallback; fidelity caveat documented.
- Preserve DB/export schema and relative image filenames.
- Mac paths: ~/Library/Application Support/PowerPointVisualArchive and ~/Library/Logs/PowerPointVisualArchive; Finder open and reveal supported.
- User-session LaunchAgent + native build/install scaffold, no privileged daemon.

## Acceptance

- [x] Pi renderer tests cover ephemeral PDF cleanup, image outputs, slide numbers, dimensions, original PPTX text/notes, and failure handling.
- [x] Pi tests cover optional LibreOffice, OS selection, Finder actions, user-data paths and config roundtrip.
- [x] Portable static preflight covers macOS app bundle and LaunchAgent scripts.
- [x] Full Pi tests green; docs and handoff current; local commit only.
- [ ] Real Mac smoke: AppleScript command, PowerPoint Automation permission, visual fidelity and hidden slides, optional LibreOffice, app bundle, LaunchAgent, login, codesign/notarization.

## M008a — Versioned image generations (shared Windows/macOS)

- Render each PPTX and PDF deck into a private staging directory under the deck asset root. Validate the full image set and page count before atomically publishing the complete generation directory.
- Store generation-specific relative paths in the existing SQLite/JSON slide image fields, never overwrite the current generation in place, and do not delete images referenced by the previous export while rebuilding.
- If PDF conversion or SQLite replacement fails, retain the previous deck/slide rows and corresponding images; remove incomplete staged generations. Do not migrate the DB schema.
- Retain previous generations until explicit garbage collection is designed and validated; additional disk use is preferable to broken active viewer image links.

## M008b — Mac install/upgrade/rollback/uninstall lifecycle

- Keep installation a deliberate per-user action; forbid mutation on non-Mac.
- Stage new app and CLI before replacing installed versions; preserve config/archive/logs. On failure restore both installed binaries and the prior LaunchAgent definition and attempt to restart prior user agent.
- Add explicit uninstall that removes only this per-user agent/plist, app and support binary; leave all user archive/config/log data intact.
- Use injectable launcher seams/tests; no claim that launchctl, TCC or PyInstaller binaries work until run natively.

## M008c — Local readiness diagnostics

- Provide an opt-in path-free local JSON report checking native OS, renderer availability, PDF/text dependencies, config validity, scan root access, output writable/space, expected app/plist presence, and pending AppleScript Automation/visual acceptance.
- No automatic telemetry or source paths, and no hidden PowerPoint launches.

## M008d — Reference PPTX and image comparison

- Generate deterministic test decks with text, picture, shape, table, chart, speaker notes, Unicode/font and a hidden slide, together with an expected metadata manifest.
- Compare two rendered image directories per-slide using pixel difference metrics and offline HTML/JSON report; identify missing/extra slides, size mismatch and threshold failure.
- Synthetic fixture generation and comparison validated on Pi; real renderer fidelity acceptance still depends on Mac/Windows outputs.
