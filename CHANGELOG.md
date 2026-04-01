# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-04-01

### Added
- Initial local-first PowerPoint archive pipeline with recursive scan, incremental change detection, SQLite index, and static viewer generation.
- PowerPoint COM slide rendering for thumbnails and previews on Windows.
- Structured slide text extraction for title, subtitle, body text, additional text, and notes.
- Viewer support for direct-open actions through the local server, slide starring, heatmap navigation, and scoped search fields.
- Folder-scoped incremental scanning with `scan --root`.

### Changed
- CLI subcommands now accept `--config` directly on each command.
- Scan logging now shows per-file progress as `(x/total)` and includes the source directory for each deck being processed.