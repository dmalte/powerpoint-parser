# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- M009 Markdown visual snippet indexing: opt-in .md scanning, heading/paragraph sections, CommonMark/tables/code rendering into offline CSP-restricted HTML previews, Pillow JPEG cards, safe iframe modal, md filter and config control, same transactional SQLite/image generations, with no raw HTML or external resources. M010 Obsidian vault-aware double-click navigation is planned separately.
- Scanner resilience: skip a file or symlink target that vanishes between directory enumeration and stat, report incomplete discovery, and defer deletions rather than aborting archive refresh or removing existing indexed records; hard I/O and permission errors still fail safely.
- Mac1 native M009 acceptance: 161 full tests, isolated Markdown/PDF snippet scan, packaged Markdown CLI, rebuilt arm64 app (17/17 artifact checks) and data-preserving install. Markdown checkbox/filter published in existing viewer, still opt-in; one vanished file was safely skipped during resumed scan.
- Phase 1 per-user desktop-agent runtime with installed config discovery, `init-config`, startup refresh, scheduled incremental refresh, localhost serving, and durable per-user logs.
- PyInstaller frozen-resource support for viewer templates/static assets.
- Windows packaging scaffold with console and windowless agent executables, a per-user Inno Setup installer, and current-user logon startup registration.
- Portable runtime/packaging tests and documented Windows smoke-test procedure.
- Phase 2 self-service agent controls: loopback status/settings/scan/restart API, browser settings page, persisted refresh interval, serialized manual/scheduled refresh, and Windows notification-area actions using existing `pywin32`.
- Large-archive viewer optimizations: derived search/file-type caching, removal of the O(n²) per-card index lookup, 240-card grid pagination with full-result modal navigation, batched DOM insertion, generated-image revalidation headers, and a deterministic 6,000-slide benchmark fixture.
- Local-only performance diagnostics: exportable browser session timing and scan/build JSONL timing records, a loopback report endpoint, and 6,000-slide Raspberry Pi headless-browser smoke verification.
- Repeatable 6,000/20,000-slide headless Chromium benchmarking harness with real frontend interaction metrics, bounded-grid assertions, and revision-tagged local JSON reports.
- Background-first agent startup with an HTTP-served first-run loading page, path-free progress fields in /api/status, and in-viewer/Settings scan progress indicators.
- M007c archive publication marker, source/config fingerprint, missing-file recovery, and no-op scan rebuild avoidance.
- M007c temporary-staged JSON/HTML/CSS/JS with per-file atomic replacement, failed-publish recovery, and concurrent-reader validation.
- M007d offline synthetic benchmark comparison dashboard and JSON output with strict compatible-revision matching, configurable warning thresholds, and history trends.
- M007e interrupted-scan recovery tests and source-safety fixes: strict scan root/traversal checks, invalid PDF rejection, transactional replacement of deck+slides, and SQLite-index-aware viewer freshness.

- M007f targeted frontend rendering: cache repeated date labels and disconnect stale image observers before replacing a slide-grid page. Benchmarked with 6,000/20,000-slide scenarios and a 50,000-slide synthetic stress case.

- M008 macOS source preparation: PowerPoint-for-Mac AppleScript temporary-PDF image backend (same JPG/PNG outputs as Windows), explicit LibreOffice option, OS-specific renderer selection, macOS Application Support/Logs, Finder open/reveal, and per-user PyInstaller/LaunchAgent build scaffolding. Native Mac acceptance remains outstanding.
- M008a shared immutable PPTX/PDF image generations with whole-directory publish, SQLite rollback safety, and retention of older images needed by active browser sessions.
- M008b staged macOS installer upgrades with rollback and explicit data-preserving uninstall; portable failure-injection tests added.
- M008c local, path-free Mac dependency/config/permission readiness reports, without triggering PowerPoint automation.
- M008d original PowerPoint reference decks (images, tables, charts, notes, Unicode, hidden slides) and offline per-slide image/size comparison in HTML and JSON.
- M008e Mac PDF-backed rendering temporarily exposes hidden slides in a private PPTX working copy, preserving original hidden flags and slide-to-notes mappings. Native Mac1 six-slide acceptance passed (6/6, 12 validated JPEGs, 15.3s, original unchanged); login agent and cross-platform image fidelity remain pending.
- M008f Mac PowerPoint renderer stages temporary PPTX/PDF in PowerPoint's own sandbox Documents directory to avoid per-presentation external-file prompts. A separate archive-side image workspace and tests preserve cleanup, hidden slides and existing Windows/LibreOffice semantics; native Mac permission validation pending.
- M008g user-controlled Pause Scan & Save / Resume Scan actions in viewer and Settings. Cooperative per-file pause checkpoints committed SQLite rows as a browsable partial HTML/JSON archive, defers deletions until a full scan, and persists pause across login/restart. Resume skips unchanged indexed decks; state/YAML persistence and HTTP controls have regression tests.
- Native Mac1 M008g acceptance: upgraded installed arm64 app preserving user data, published 2,959 decks / 15,809 slides in browsable HTML/JSON, and validated 4-file Resume/Pause/restart with a separate PDF-only user agent. Production stays paused until user action.

### Changed

- Mac1 native acceptance preparation: Apple Silicon PyInstaller app and CLI build passed, bundled PDF ingestion/viewer passed, and strict ad hoc code-signature verification passed. Added opt-in PowerPoint-native smoke command and documented unresolved -9074 PDF export failure; no LaunchAgent installed.


- M004a cross-platform Windows packaging source/artifact preflight with local JSON diagnostics, release-version checks and fail-fast native build script validation. Windows installer smoke remains unverified.
- Local viewer serving now uses a loopback-only `ThreadingHTTPServer` so static assets and control requests can be handled concurrently.
- Agent no longer blocks the HTTP server on first indexing; initial scans use the same serialized worker as manual refreshes.
- Archive JSON is sent with no-store semantics and opened-file streaming rather than second-resolution conditional caching, preventing a stale 304 response after a quick publication.

### Notes
- Windows executable/installer/PPTX smoke validation is still pending; REQ-DEPLOY-001 / M004 remain unvalidated on Windows.
- Windows notification-area/menu behavior is implemented with portable/structural coverage but still requires packaged Windows smoke validation; REQ-DEPLOY-002 / M005 remain unvalidated on Windows.
- The 6,000-slide synthetic fixture is validated structurally, but representative Edge/Chrome timing and memory measurements are still pending; REQ-PERF-001 / M007 remain active.

## [0.2.0] - 2026-04-02

### Added
- **Advanced search**: quoted phrases (`"budget report"`), multi-term AND (`budget report`), and explicit AND keyword support in the viewer.
- **Wrap per deck**: new "Wrap per deck" checkbox in the grid toolbar forces each presentation's thumbnails to start on a new row.
- **PDF support**: scan, render, and index PDF files alongside PowerPoint. Uses PyMuPDF for text extraction and page rendering (no COM needed for PDFs).
- New `file_types` config option to select which file types to scan (`pptx`, `pdf`, or both).
- `PyMuPDF>=1.23` added as a dependency.

## [0.1.0] - 2026-04-01

### Added
- Initial local-first PowerPoint archive pipeline with recursive scan, incremental change detection, SQLite index, and static viewer generation.
- PowerPoint COM slide rendering for thumbnails and previews on Windows.
- Structured slide text extraction for title, subtitle, body text, additional text, and notes.
- Viewer support for direct-open actions through the local server, slide starring, heatmap navigation, and scoped search fields.
- Folder-scoped incremental scanning with `scan --root`.
- Heatmap window controls for `Last 12 months` and per-year views such as `2026` and `2025`.
- MIT license and publish-safe repo defaults for local config, generated output, and virtualenv artifacts.

### Changed
- CLI subcommands now accept `--config` directly on each command.
- Scan logging now shows per-file progress as `(x/total)` and includes the source directory for each deck being processed.
- README and viewer documentation now reflect the `.venv` workflow, scoped scans, direct-open support, stars, and heatmap range selection.
- M011: searchable expandable directory tree with recursive document/snippet counts and multi-include/exclude viewer filtering, without changing scan roots or SQLite.
- M011: Markdown previews and section thumbnails display safely decoded local images, including direct Obsidian vault-relative image paths. Assets are copied into immutable versioned generations; remote/unsafe images remain placeholders under restrictive iframe/CSP. Existing Markdown previews reprocess once for renderer upgrade.
