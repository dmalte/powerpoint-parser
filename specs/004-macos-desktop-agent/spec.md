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
