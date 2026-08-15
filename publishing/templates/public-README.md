# PowerPoint Visual Archive Viewer

A local-first tool that scans directories of PowerPoint and PDF files, exports slide/page thumbnails, extracts metadata, and generates an HTML visual browser for fast slide discovery.

## Requirements

- Python 3.10+
- Microsoft PowerPoint on Windows for PPTX rendering via COM automation
- PDF workflows work cross-platform

## Installation

```bash
python -m venv .venv
python -m pip install -e .
```

On Windows, activate the virtual environment before using the CLI.

## Quick Start

Copy the example configuration and edit the scan roots and output directory:

```bash
copy config\config.example.yaml config.yaml
```

Then scan, build, and optionally serve the archive:

```bash
pptviewer scan --config config.yaml
pptviewer build --config config.yaml
pptviewer serve --config config.yaml --port 8080
```

The scanner is incremental by default and reprocesses only changed files. Use `--root` one or more times to limit a scan to selected folders without treating indexed decks outside that scope as deleted.

## CLI Commands

- `scan` — scan folders, export slide images, and update the index
- `build` — regenerate the static HTML viewer
- `serve` — run a local HTTP server for the generated viewer
- `clean` — remove orphaned assets and purge deleted deck records
- `rebuild` — fully reprocess files and rebuild the viewer

Common options include `--config PATH` and `-v/--verbose`. The `scan` command also supports `--force` and repeatable `--root PATH`.

## Configuration

See `config/config.example.yaml` for the available settings, including scan roots, file types, exclusions, output directory, render sizes/quality, and incremental-processing behavior. The real `config.yaml` is intentionally ignored because it normally contains machine-specific paths.

## Viewer Features

The generated viewer supports text search and search scopes, date filters, browser-local starred slides, folder/presentation navigation, thumbnail grouping, PowerPoint and PDF content, a calendar heatmap, slide detail previews, links to originals when served locally, and keyboard navigation.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/test_core.py -v
```

## License

MIT. See [LICENSE](LICENSE).
