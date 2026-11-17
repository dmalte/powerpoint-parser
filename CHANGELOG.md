# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- M013 establishes a separate **private** canonical GitHub development repository with protected Pi/Mac1 origins and repo-specific Mac1 SSH authentication. The existing public repository is a manual-review-only release target. A hardened committed-source whitelist exporter, high-severity private-data scanning and independent public-history local review workflow passed 208 Pi/208 Mac1 tests plus curated public source tests; no public GitHub change occurred.
- M008i hardening processes PDFs ahead of GUI-dependent PowerPoint to persist encrypted-file holds even if the first Office automation job blocks.
- M008i durable conversion retry policy: unchanged encrypted PDFs held from scheduled retries; changed/forced/manual resets recover. PowerPoint/permission/timeouts get bounded 5m/30m/2h/6h backoff across restarts. Path-free private retry-state sidecar, fail-open corrupted-state handling, numeric status summaries, Settings reset action and local CLI. Native Mac1 passed 202/202 tests, 17/17 package preflight and codesign; installed with verified backups and preserved config/SQLite. Latest scan suppressed 58 encrypted PDFs and 4 PPTX backoffs, processed zero files and skipped unnecessary viewer export.
- M008h path-free conversion-failure CLI: bounded latest-scan agent-log parser that reports only file-type/category counts and advisory retry recommendations; supports local JSON output, no source paths/private exception text, no changes to the existing scan retry schedule.
- M012 single US Letter Markdown preview: one 816×1056 JPEG first-page preview and matching 408×528 portrait thumbnail per Markdown document, regardless of headings; full-document text stays searchable. PyMuPDF Story positions safely re-encoded local/explicit Obsidian images into the actual first-page layout; later-page images are absent. Existing HTML section previews stay viewable during Markdown-only signature-based reindexing, with no PDF/PPTX schema or processing changes. Native Mac1 accepted (177/177 tests, 17/17 bundle preflight, codesign, packaged CLI Obsidian-image fixture, verified backup and staged upgrade); production Markdown migration completed successfully (10,758/10,758 first-page JPEGs, zero active HTML section rows). The 62 failed files were unrelated PPTX/PDF conversions; 1 vanished source deferred deletion reconciliation. Legacy asset generations remain retained.
- M007h bounded presentation sidebar: 100-row pagination with full-library filename search, keyboard/click selection, range/page navigation, empty-state controls and delegated list handlers; live DOM and sidebar-row measurements plus Node/CDP acceptance coverage. No index or archive format changes.
- M007h Mac1 acceptance: 174/174 source tests, 17/17 native package checks and strict signature verification; deployed after verified backup. Headless Chrome on 145,289 snippets measured 81.4% fewer live DOM elements (17,901 → 3,330). JS heap remained approximately 1 GiB. Existing unpaused scan setting was restored; a stalled PowerPoint first-file conversion is tracked separately.
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

- M007i reduced retained browser search-heap by avoiding duplicated body/extracted-text strings and prewarming the default-scope cache. Three shadow Mac1 Chrome runs measured ~992 → ~501 MiB retained after GC; installed native arm64 app confirmed 500.86–500.87 MiB, comparable 135–139 ms search p95. Full Pi/Mac 179/179 tests and 17/17 Mac packaging checks passed; SQLite/config backup verified and original scan preference restored. Public export/SQLite schemas unchanged.

- M007c failed-only scans now avoid re-exporting the viewer when all new/changed candidates fail and the existing SQLite/publication marker is current. Successful processing, applied deletions, initial publication, stale markers, and explicit pause still rebuild; regression coverage added.
- M007c Mac1 native upgrade passed 17/17 packaging checks after source/Pi 172-test validation. Preserved a verified local SQLite/YAML backup; a live failed-only incremental scan retried 69 files, committed zero, skipped the ~395 MiB export rebuild, and returned cleanly.
- M007g native Mac1 Chrome benchmarks captured 6k/20k/50k synthetic workloads and two read-only runs against ~142k real snippets. Initial interaction measured ~1.22–1.34 s, with ~986–1,000 MiB JS heap; memory/DOM profile and Windows acceptance remain open.

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

- M011 native Mac1: 170 tests passed, 17/17 package preflight, verified offline Markdown images from source and packaged CLI, data-preserving installed upgrade and live directory UI. Earlier Markdown snippets are reprocessing on the restored background scan.
