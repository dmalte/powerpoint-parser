# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
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

### Changed
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