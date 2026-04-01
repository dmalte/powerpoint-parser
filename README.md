# PowerPoint Visual Archive Viewer

A local-first tool that scans directories of PowerPoint files, exports slide thumbnails, extracts metadata, and generates an HTML-based visual browser for fast slide discovery.

## Requirements

- Python 3.10+
- Microsoft PowerPoint (installed, for slide rendering via COM automation)
- Windows (COM automation is Windows-only)

## Installation

```bash
. .\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

If `.venv` does not exist yet, create it first:

```bash
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Quick Start

1. **Create a config file** — copy and edit the example:

```bash
copy config\config.example.yaml config.yaml
```

Edit `config.yaml` to point `scan_roots` at your PowerPoint folders and set `output_dir`.
Use forward slashes in YAML paths on Windows, for example `D:/Slides`, or single quotes if you want to keep backslashes.
`config.yaml` is intentionally ignored by Git because it usually contains local machine paths.

2. **Scan and process** — export thumbnails and build index:

```bash
pptviewer scan --config config.yaml
```

3. **Build the viewer** — generate the static HTML:

```bash
pptviewer build --config config.yaml
```

4. **View** — either open `output/index.html` directly, or start a local server:

```bash
pptviewer serve --config config.yaml --port 8080
```

Then open http://127.0.0.1:8080 in your browser.

## CLI Commands

| Command   | Description |
|-----------|-------------|
| `scan`    | Scan folders, export slide images, update index. Only reprocesses changed files. |
| `build`   | Regenerate the HTML viewer from the existing index. |
| `serve`   | Start a local HTTP server pointing at the output directory. |
| `clean`   | Remove orphaned assets and purge deleted deck records. |
| `rebuild` | Full reprocess of all files + regenerate viewer. |

If `pptviewer` is still not found in PowerShell, either the virtualenv is not activated or the terminal was opened before activation. Use the explicit launcher instead:

```bash
.\.venv\Scripts\pptviewer.exe scan --config config.yaml
```

### Common Options

- `--config PATH` — Path to YAML config file (default: `./config.yaml`)
- `-v / --verbose` — Enable debug logging

### Scan Options

- `--force` — Reprocess all files regardless of change detection

## Configuration

See [`config/config.example.yaml`](config/config.example.yaml) for all options:

- `scan_roots` — list of directories to scan recursively
- `exclude_dirs` — directory names to skip (e.g. `.git`)
- `exclude_patterns` — filename glob patterns to skip (e.g. `~$*.pptx`)
- `output_dir` — where thumbnails, index, and HTML are written
- `render.thumbnail_width` — thumbnail width in pixels (default 320)
- `render.preview_width` — preview width in pixels (default 1280)
- `render.jpeg_quality` — JPEG quality 1-100 (default 82)
- `processing.incremental` — skip unchanged files (default true)
- `processing.purge_deleted` — remove assets for deleted files (default true)

## Viewer Features

- **Search** — filter by deck name, folder, slide title, or extracted text
- **Quick filters** — Today, This Week, This Month
- **Sidebar** — browse by folder or presentation
- **Thumbnail grid** — lazy-loaded, grouped by deck/day/week
- **Calendar heatmap** — click any day to filter to that date
- **Slide detail modal** — preview, metadata, open original file
- **Keyboard navigation** — arrow keys in modal, Escape to close

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/ -v
```

## License

MIT. See [LICENSE](LICENSE).
