# PowerPoint Visual Archive Viewer

A local-first tool that scans directories of PowerPoint and PDF files, exports slide/page thumbnails, extracts metadata, and generates an HTML-based visual browser for fast slide discovery.

## Requirements

- Python 3.10+
- Microsoft PowerPoint (installed, for PPTX slide rendering via COM automation)
- Windows (COM automation is Windows-only; PDF support works cross-platform)
- [PyMuPDF](https://pymupdf.readthedocs.io/) (installed automatically, used for PDF rendering)

## Installation

```bash
. .\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

On Linux, including Raspberry Pi, installation works but PowerPoint slide rendering does not. You can still use PDF scanning and the viewer; `.pptx` rendering requires Windows with Microsoft PowerPoint installed.

### Windows installer source preflight

Run python scripts/preflight_windows_package.py on Linux/macOS/Windows to check the package definitions and bundled frontend assets without building or running Windows binaries. For a local JSON report, add --json .runtime/packaging/preflight.json. The Windows build script invokes preflight automatically before and after packaging. A pass does **not** certify an installer; real Windows and PowerPoint smoke tests remain pending.

### Windows packaged deployment (Phase 1 in progress)

The project now includes the Phase 1 per-user desktop-agent runtime and Windows packaging definitions under `packaging/windows/`. The installed design uses a windowless agent in the signed-in user's session rather than a Windows Service, keeps writable data under per-user application data, and can start automatically at user logon.

The packaging scaffold has portable structural/test coverage, but the Windows installer/PPTX smoke test is still pending. Treat it as an in-progress deployment path until that validation is recorded. See `packaging/windows/README.md` for build and smoke-test steps.

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

Edit `config.yaml` to point `scan_roots` at your PowerPoint/PDF folders and set `output_dir`.
Use forward slashes in YAML paths on Windows, for example `D:/Slides`, or single quotes if you want to keep backslashes.
`config.yaml` is intentionally ignored by Git because it usually contains local machine paths.

2. **Scan and process** — export thumbnails and build index:

```bash
pptviewer scan --config config.yaml
```

Repeat the same command later and it will only reprocess changed files. Unchanged decks are skipped.
During processing, the scanner logs per-file progress as `(x/total)` and shows the source directory for each deck.

If you only want to refresh part of the archive, scope a run to one or more folders:

```bash
pptviewer scan --config config.yaml --root D:/Slides/ClientA --root D:/Slides/ClientB
```

Scoped scans stay incremental and only treat missing files inside the selected folders as deleted. Indexed decks outside that scan scope are left unchanged.

3. **Build the viewer** — generate the static HTML:

```bash
pptviewer build --config config.yaml
```

4. **View** — either open `output/index.html` directly, or start a local server:

```bash
pptviewer serve --config config.yaml --port 8080
```

Then open http://127.0.0.1:8080 in your browser.

Use `serve` when you want the viewer to open the original `.pptx` or its containing folder directly from the web UI. Browsers are inconsistent about `file:///` access, so the local server is the reliable mode for those actions.

## CLI Commands

| Command | Description |
|---|---|
| `init-config` | Create a per-user configuration and archive directory without hand-editing YAML; accepts repeatable `--root` folders. |
| `agent` | Run the long-lived per-user runtime: incremental refresh, viewer build, localhost server, and optional periodic refresh. |
| `scan` | Scan folders, export slide images, update index. Only reprocesses changed files. |
| `build` | Regenerate the HTML viewer from the existing index. |
| `serve` | Start a local HTTP server pointing at the output directory. |
| `clean` | Remove orphaned assets and purge deleted deck records. |
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
- `--root PATH` — Limit a scan run to one or more folders without touching indexed decks outside that scope

### Agent Options

- `--port PORT` — Local viewer port (default 8080)
- `--scan-interval SECONDS` — Optional one-run override for the persisted incremental refresh interval; `0` disables periodic refresh

The agent starts serving HTTP immediately, while the initial scan and viewer build run on a background worker. A fresh installation first shows a **Preparing your slide archive** page with live phase/file-count updates, and opens the actual viewer after the initial build finishes. An already built archive remains browseable while periodic/manual scans continue. The topbar and Settings show progress; a failed scan leaves the server up with an error status. Scans remain serialized, so clicking Scan Now while a scan is running reports that it is busy.

When the agent is running, open `http://127.0.0.1:8080/settings.html` (or click **Settings** in the viewer) to see agent status, trigger **Scan Now**, open logs, restart the agent, and edit scan folders, file types, and the persisted refresh interval without touching YAML. On Windows, the installed agent also exposes the same common actions from a notification-area icon.

With no explicit `--config`, existing development locations are checked first, followed by the per-user installed config location. On Windows that default is `%LOCALAPPDATA%\PowerPointVisualArchive\config.yaml`; the default archive and logs live beside it under `archive` and `logs`.

## Configuration

See [`config/config.example.yaml`](config/config.example.yaml) for all options:

- `scan_roots` — list of directories to scan recursively
- `exclude_dirs` — directory names to skip (e.g. `.git`)
- `exclude_patterns` — filename glob patterns to skip (e.g. `~$*.pptx`)
- `file_types` — list of file extensions to scan: `pptx`, `pdf`, or both (default: `["pptx"]`)
- `output_dir` — where thumbnails, index, and HTML are written
- `render.thumbnail_width` — thumbnail width in pixels (default 320)
- `render.preview_width` — preview width in pixels (default 1280)
- `render.jpeg_quality` — JPEG quality 1-100 (default 82)
- `processing.incremental` — skip unchanged files (default true)
- `processing.purge_deleted` — remove assets for deleted files (default true)
- `processing.scan_interval_seconds` — automatic agent refresh interval (default 1800; `0` disables automatic refresh)

## Viewer Features

- **Search** — filter by deck name, folder, slide title, or extracted text; supports quoted phrases (`"budget report"`), multi-term AND (`budget report`), and explicit AND (`budget AND report`)
- **Search scopes** — limit search to deck, folder, title, subtitle, slide text, additional text, or notes
- **Quick filters** — Today, This Week, This Month
- **Stars** — star slides locally in the browser and filter to starred slides only
- **Sidebar** — browse by folder or presentation
- **Thumbnail grid** — lazy-loaded, grouped by deck/day/week, and paginated to at most 240 live cards for large archives; optional "Wrap per deck" to start each presentation on a new row
- **PDF support** — scan, render, and browse PDF pages alongside PowerPoint slides
- **Calendar heatmap** — switch between the last 12 months or a specific year, then click any day to filter to that date
- **Slide detail modal** — preview, metadata, open original file, open containing folder
- **Keyboard navigation** — arrow keys in modal, Escape to close
- **Agent settings** — localhost status/settings page for Scan Now, roots, file types, refresh interval, logs, and restart while the agent is running
- **Windows tray controls** — Open Archive, Scan Now, Settings, View Logs, Restart, and Exit from the notification area

## Performance diagnostics and feedback

The viewer includes built-in, **local-only** performance measurements (M007).
After changing the source JS/templates, run `pptviewer build --config config.yaml`
(or restart the installed agent) to regenerate `index.html` and the bundled scripts.

1. Open the viewer in the browser, preferably through `pptviewer serve` or `pptviewer agent`.
2. Click **Performance** in the top bar. It shows measurements from the current browser session.
3. Exercise actual workflows: search for text, change sorting/grouping, paginate, scroll, and open previews.
4. Click **Refresh** to inspect p50/p95/max timings or **Download JSON report** to save a report for analysis. **Clear samples** starts a new interaction measurement window (but does not reload navigation stats).

The report includes navigation/init timing; JSON fetch, reading and parsing; data normalization; text search, filtering, sorting, grid generation; thumbnail and preview load times; observed scroll-frame gaps, browser long tasks, and optional Chromium JS heap usage. Browsers without heap/long-task support report those fields as unavailable. p50 and p95 cover up to the most recent 200 samples per operation. This instrumentation measures the real session rather than a synthetic wall-clock estimate.

Scan/build processing also records aggregated, monotonic timing stages and numeric file/page counts in `performance.jsonl`, under the user's app-data log directory:

- Windows: `%LOCALAPPDATA%\PowerPointVisualArchive\logs\performance.jsonl`
- Linux: `~/.local/share/PowerPointVisualArchive/logs/performance.jsonl` (unless `XDG_DATA_HOME` is configured)

The loopback server exposes the most recent 20 backend performance records through `GET /api/performance` (no authentication, only locally accessible); browser JSON downloads include these records when the endpoint is available. When the HTML is opened without the built-in server, exports still contain browser measurements but cannot include backend records.

**Privacy:** No automatic uploads, cloud endpoint, saved search queries, slide content, deck names, source paths, or individual user files are included in performance records. The downloaded report does include browser/version information and library-size counters. Review the file before sharing it outside your system.

**Validation status:** 6,000-slide headless Chromium smoke testing has passed on Raspberry Pi; **company-class Windows Chrome/Edge acceptance measurements are still required**. The Pi measurements are not Windows performance targets or a Windows installer validation.

### Automated synthetic browser benchmark (M007a)

On a development machine with project dependencies, **Node.js 22+** and **Chromium/Chrome/Edge**, run:

```bash
python scripts/benchmark_viewer.py --slides 6000 20000 --iterations 5
```

This command generates deterministic **synthetic** archives using the actual viewer templates and JS. A headless browser measures initial readiness and scripted search/filter, sort, pagination and modal interactions, plus DOM/card counts and available JS heap. It writes JSON reports under `.runtime/benchmarks/` containing the Git revision, browser version, dataset size and in-page metrics (excluded from Git). Set `--browser /path/to/chrome` and `--output-dir DIRECTORY` when necessary; Node.js is a development/test dependency, not a packaged application requirement.

The synthetic fixtures deliberately use a **shared placeholder JPEG**. The timings are suitable for tracking frontend regressions but **do not measure realistic thumbnail fetching/decoding, PowerPoint rendering, initial library ingestion, or Windows end-user acceptance**. Use the built-in Performance report on real content for those measurements.

The first Pi run (6 search iterations, 1,000 characters per slide) measured approximately 953 ms initial viewer readiness and 131 ms p95 filter-to-grid at 6,000 slides; 1,377 ms and 195 ms respectively at 20,000 slides. Both retained at most 240 grid cards. These are environment-specific baselines, not release budgets.

### Incremental refresh and safe publication (M007c)

The background agent now skips viewer generation when the filesystem scan reports no new, changed, or deleted documents **and** the current publication is complete. The first scan after an upgrade from a legacy archive refreshes the HTML/JSON once to establish its freshness marker. Missing generated assets, modified frontend sources, or a changed viewer title also trigger a rebuild, even when document files are unchanged.

A rebuild prepares JSON, templates, CSS and JavaScript in a temporary directory. Each complete file is then atomically substituted into the live archive; the first-run index page is published after JSON and scripts are available. A small private `.viewer-build.json` marker records the final generated-file timestamps/sizes and a fingerprint of the bundled frontend/configuration. The marker is written last; if publication fails, the next refresh detects it and tries again. Existing CSS/JS directories are not deleted while clients are reading them.

The built-in HTTP server and browser always request `data/export.json` without cache reuse, avoiding incorrect same-second 304 Not Modified replies when an export changes. An unchanged scan still performs filesystem discovery, but it avoids the expensive SQLite export, JSON serialization, and frontend file generation. The status response reports `last_summary.viewer_rebuilt` (true/false) so the UI can distinguish a no-change check from an update.

**Scope:** This is atomic **per file**, not an ACID transaction across multiple browser requests, SQLite operations, or PDF/PPTX image files. Browser sessions spanning the brief publication window can observe multiple complete generations. Real Windows packaging/PowerPoint and large-library hardware measurements are still pending.

### Performance history and regression comparison (M007d)

The offline regression reporter compares saved synthetic 6,000/20,000-slide benchmarks across **different clean Git revisions**:

    python scripts/benchmark_history.py --thresholds config/performance_thresholds.example.json

This creates ignored local files at .runtime/benchmarks/history.html and .runtime/benchmarks/comparisons.json. The HTML report shows latest compatible revisions, timing/memory changes, trend graphics and unmatched runs. Comparable runs must have the same operating system, architecture, full browser version, slide count, generated text length and search workload. A dirty or unknown working-tree report is shown in history but not used as an automatic baseline.

The JSON thresholds file maps each metric to the maximum percentage increase that triggers a **warning**. Missing metrics and p95 measurements with fewer than five observations are inconclusive, not regressions. Default invocation returns success even with warnings. Use --fail-on-warning only for a controlled, repeatable CI environment; this returns exit code 2 when warnings exist. No telemetry is uploaded. This is a synthetic frontend regression tool, not a substitute for real-image or Windows acceptance tests.

### Recoverable scans and indexed data (M007e)

A missing or inaccessible scan root is treated as a failed scan, not an empty folder. This prevents detached drives or permission errors from triggering mass deletions of previously indexed material. Corrupt/unreadable PDFs are reported as failed documents; previously indexed deck metadata and slides remain available for a later retry.

Changed decks are committed to SQLite as a **single deck-plus-slides transaction** after processing completes; failed replacement inserts roll back. The .viewer-build.json freshness marker also includes a checksum of the indexed deck inventory. If processing committed changes but the process stopped before the viewer regenerated, the next incremental run detects that mismatch and rebuilds even when the filesystem scan reports no changes.

Staged export errors, including simulated disk-full conditions, preserve the last complete output and trigger a retry. Real PowerPoint COM rendering and the overwriting of in-place thumbnail images are not transactionally isolated by this work; fully versioned image generations and power-loss durability require separate design/Windows acceptance.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/ -v
```

## License

MIT. See [LICENSE](LICENSE).
