# Design Spec

## Goal

Build a local-first PowerPoint and PDF visual archive for fast slide/page discovery without opening large source files. The app scans one or more folders, exports slide/page imagery, extracts lightweight metadata, stores it in SQLite, and generates a local HTML viewer optimized for visual retrieval.

## Product Boundaries

In scope:
- Recursive `.pptx` and `.pdf` scanning across multiple roots
- Incremental change detection by path, file size, and modified timestamp
- Slide/page thumbnail and preview export
- PowerPoint slide and PDF page metadata extraction
- Static HTML viewer with local filtering and search
- Windows-first local file opening via the optional built-in server
- PDF-only installation and use on non-Windows platforms

Out of scope:
- Editing PowerPoint files
- Cloud sync, accounts, or collaboration
- OCR, semantic search, or AI-heavy indexing
- Browser upload flows

## Locked Decisions

- PowerPoint rendering source: Microsoft PowerPoint COM automation on Windows
- PDF rendering and text extraction: PyMuPDF
- PowerPoint metadata extraction: `python-pptx`
- Persistent index: SQLite
- Viewer architecture: static HTML/CSS/JS generated from indexed data
- Activity date semantics: deck file modified time
- Incremental behavior: unchanged decks are skipped; changed decks are fully rebuilt
- File discovery fails without mutating index data if any scan root is missing or traversal/stat is incomplete. Corrupt PDFs do not replace previously indexed document rows.
- Replacement deck metadata and slide rows now commit in one SQLite transaction after successful extraction, retaining old rows if processing or SQL fails.
- Agent viewer generation is skipped on no-change scans only when a persisted publication marker matches bundled frontend/config, expected output file timestamps/sizes, and a digest of active SQLite deck signatures/slide counts. Explicit CLI build/rebuild still regenerate.
- Output generation uses same-volume staging, individual atomic file replacement, and a last-written completion marker. Publishing the viewer entrypoint after the JSON/scripts protects first-load requests; the promise is per-file integrity, not multi-resource atomicity.
- Scoped rescans: selected folders can be rescanned without affecting decks outside the chosen scope

## Architecture

Pipeline:
1. Scan configured roots for enabled `.pptx` and `.pdf` file types
2. Detect new, changed, unchanged, and deleted documents
3. Export PowerPoint slide imagery via COM on Windows or PDF page imagery via PyMuPDF
4. Extract structured text and metadata with the format-specific processor
5. Upsert documents and slides/pages into SQLite
6. Export JSON and render the static viewer

Runtime surfaces:
- CLI for `scan`, `build`, `serve`, `clean`, and `rebuild`
- Loopback-only threaded HTTP server for static viewer delivery, browser-safe local open actions, agent status/settings, manual scan, logs, and shutdown/restart control
- Static frontend for search, filters, heatmap, preview modal, starring slides, and agent settings/status
- Windows per-user desktop agent that owns startup refresh, viewer generation, serialized scheduled/manual refresh, the local server, per-user logging, and a notification-area control surface while running in the signed-in user's interactive session
- The agent now binds HTTP before the initial (potentially long) indexing completes. A static loading page is served if no index exists yet, with numeric phase and progress from /api/status; an existing index stays available during refresh. Initial, manual and scheduled refreshes share a single lock.

## Data Model

### Deck
- `deck_id`
- `file_path`
- `file_name`
- `folder_path`
- `file_size`
- `modified_time`
- `processed_time`
- `slide_count`
- `file_signature`
- `status`

### Slide
- `slide_id`
- `deck_id`
- `slide_number`
- `title`
- `subtitle_text`
- `body_text`
- `extra_text`
- `extracted_text`
- `notes_text`
- `thumb_path`
- `preview_path`
- `width`
- `height`

## Search and Retrieval

Search targets:
- Deck name
- Folder path
- Slide title
- Slide subtitle
- Slide body placeholder text
- Additional freeform text boxes and table text
- Notes text

Viewer behavior:
- Client-side filtering on exported JSON
- Search scopes are user-selectable in the UI
- Stars are stored locally in browser storage and can be filtered or prioritized in sorting

## File Opening Strategy

Direct `file:///` links are unreliable in browsers, especially when served over HTTP. The app therefore supports two modes:
- Static fallback: attempt `file:///` open when the viewer is opened directly from disk
- Preferred local mode: use the built-in `serve` command, which exposes local endpoints that open the original `.pptx` or containing folder on Windows

## Windows Deployment Architecture

The accepted company rollout uses three phases:

1. **Packaged desktop agent and installer.** The runtime foundation now provides per-user paths/config bootstrap, a long-running agent, scheduled refresh, packaged-resource lookup, and durable logs. Windows PyInstaller/Inno Setup definitions package that runtime for per-user installation and user-logon startup; Windows build/install/PPTX smoke validation is still required before this phase is considered complete. PowerPoint COM automation remains in the signed-in user's interactive session rather than a Windows Service.
2. **Self-service controls.** The agent now exposes loopback-only status/settings/scan/shutdown controls, generates a browser settings page, persists scan roots/file types/refresh interval to the existing YAML config, serializes manual and scheduled refreshes, and starts a Windows notification-area menu using existing `pywin32` for Open Archive, Scan Now, Settings, View Logs, Restart, and Exit. Windows packaged tray behavior still requires smoke validation.
3. **Enterprise distribution.** Add signing, silent installation, managed defaults, diagnostics/version reporting, and an update/distribution path suitable for corporate endpoint management.

The local-first architecture remains unchanged: source files and generated archive data stay on the user's machine unless a future accepted requirement explicitly introduces shared or cloud storage. A central multi-user server is not part of this rollout.

## Performance Diagnostics

- `web/static/js/performance.js` provides bounded, in-memory browser sampling using `performance.now()`, Navigation Timing, and supported Long Task/heap APIs. `app.js` measures fetch/read/JSON parsing, normalized search, filter/sort, grid rendering, image loading, modal opening and interactions. A scroll-only animation-frame sampler records frame gaps.
- The top-bar Performance panel displays measurements. Only the user's explicit Download action saves a JSON report; no background transport or persistent browser telemetry is introduced.
- `TimedRun` in `src/ppt_visual_archive/perf_metrics.py` aggregates timings for filesystem scans, change detection, PPTX/PDF rendering/extraction, SQLite upserts, and static viewer builds. Per-user `logs/performance.jsonl` stores bounded-size local JSONL records with only operation labels, numeric counts and stage durations.
- `GET /api/performance` on the existing loopback-only server returns up to 20 recent backend records, allowing downloads to combine browser and backend evidence without exposing source paths or raw logs.
- A cross-platform, dependency-light development harness (`scripts/benchmark_viewer.py` + `scripts/measure_viewer.mjs`, Node.js 22+ CDP) exercises the real viewer using deterministic synthetic datasets, scripted interactions, per-revision reports, and bounded DOM assertions at 6,000/20,000 slides. The shared JPEG placeholders intentionally do not represent real thumbnail performance.
- Initial indexing now happens on a worker before/while the built-in HTTP server starts; / and /index.html serve a static first-run loading page until index.html exists. The agent exposes counts/phase, not paths, as progress in /api/status; Settings and viewer show progress while an update runs.
- The indexed web archive is staged in a hidden temporary directory, then CSS/JS, settings, JSON, and index page are swapped individually using os.replace. The private .viewer-build.json marker holds source/config fingerprint and published sizes/timestamps; a missing/mismatched marker forces regeneration. Output directories remain present throughout publication.
- The built-in server streams a single opened export file without conditional Last-Modified validation and sends Cache-Control: no-store; the browser requests the export with no-store to avoid stale same-second 304s.
- Real acceptance budgets for Windows Edge/Chrome remain pending. Headless Chromium running on Raspberry Pi is an instrumentation smoke test, not representative hardware validation.

- M007f rendering optimization caches locale-formatted dates and disconnects IntersectionObserver subscriptions for offscreen images on each grid redraw, retaining the 240-card page bound. No search API/schema changes; very large single JSON exports remain a scaling consideration.

## macOS Renderer and Deployment Architecture (M008)

- Windows PPTX: the established PowerPoint COM image renderer is unchanged.
- Mac PPTX: PowerPoint for Mac AppleScript saves a temporary PDF; a PyMuPDF adapter creates the same thumbnail/preview JPG/PNG files. python-pptx reads text, structured fields and speaker notes from the original PPTX. Converted PDFs are not persisted.
- Alternate renderer: user can explicitly choose LibreOffice headless PPTX-to-temporary-PDF conversion; no silent fallback because fidelity can change.
- All slide rendering implementations expose start/stop/export_slides; the same pipeline and SQLite/export/viewer remain in use. Slide-count mismatch or missing converter output rejects reindexing.
- macOS source paths reside under Application Support and Logs. Finder open/reveal and view-logs use argument-vector process execution, not a shell.
- Native packaging source includes a PyInstaller Mac app and CLI, and an explicit per-user LaunchAgent installer; no LaunchDaemon, sudo, or system-wide Service. Automation consent and the native bundle must be verified on a Mac before M008 can be accepted.
- Direct Mac AppleScript JPEG image export is not confirmed; PowerPoint GUI JPEG export is not evidence of a scriptable command. Temporary PDF preserves the same final images and reuses the established PyMuPDF rasterizer.

## Performance Notes

- Incremental scanning avoids unnecessary rerendering.
- Thumbnails are lazy-loaded with `IntersectionObserver`, so off-screen slide images are not fetched immediately.
- The viewer still fetches one complete `data/export.json` and filters/sorts the entire slide array in browser memory, but it no longer renders the complete matching result set into the DOM.
- The previous `renderGrid()` per-card `slides.indexOf(slide)` hotspot has been removed; filtered indexes are assigned once after sorting.
- Lazy image loading is combined with fixed-size grid pagination, so a 6,000-slide result creates at most 240 slide cards at once rather than 6,000 card subtrees.
- A synthetic 6,000-slide export using the current JSON schema measured approximately 4.7 MB with light text, 12.7 MB with moderate text, and 29.9 MB with heavy extracted text. These are sizing probes rather than browser acceptance measurements; real archives must be benchmarked on representative Windows laptops.
- At the 5,000–6,000 slide target, the frontend-first optimization is now implemented: derived file/search fields are normalized once, scoped search blobs are cached, the accidental per-card O(n²) `indexOf` lookup is removed, page renders use a `DocumentFragment`, and the grid is hard-bounded to 240 cards while modal navigation still spans the full filtered result set.
- The localhost server now uses `ThreadingHTTPServer`. Generated deck image responses use browser revalidation cache headers, `export.json` uses `no-store`, and control API responses remain `no-store`. Real image-request behavior still needs representative Windows browser measurement.
- Keep SQLite as the authoritative index. Do not introduce a database-backed search API solely for the 6,000-slide target unless measured browser/data-loading results justify it. If archives later grow well beyond the target or exported JSON becomes materially large, a second-stage design may split summary/search data from slide details or expose paginated/query endpoints backed by SQLite.

### Planned Large-Archive Optimization Sequence

M007 / REQ-PERF-001 should begin with a reproducible 6,000-slide benchmark and then apply optimizations in this order:

1. **Eliminate avoidable frontend work.** Replace per-card `indexOf`, cache normalized searchable text and file-type/date derivatives, avoid repeated whole-array transformations where possible, and use document fragments/batched DOM updates.
2. **Bound rendered DOM.** Prefer virtualized/windowed rendering or incremental pages/chunks while preserving modal navigation, grouping, starring, and filtering semantics. The browser should not keep one full card subtree per archive slide.
3. **Tune static serving.** Measure concurrent thumbnail/preview requests, then consider a threaded local HTTP server, immutable/cache-friendly headers for generated image assets, and appropriate cache invalidation after rebuilds.
4. **Reduce initial data cost only if needed.** If the single export remains a material startup/memory bottleneck after DOM work, split lightweight browse/search metadata from full slide details, compress/serve data efficiently, or move query/pagination to the local backend while continuing to use SQLite.
5. **Validate on real hardware.** Record initial interactive time, search/filter/sort latency, scroll smoothness, DOM/card count, browser memory, JSON size/parse cost, and image-request behavior on representative company Windows laptops.

## Risks

- PowerPoint COM can be slow or brittle on corrupted decks and is unavailable on non-Windows hosts
- Browser security rules limit local file access without the local server
- Very large archives may outgrow a single exported JSON file
- Cross-platform behavior must not accidentally make pywin32 a required dependency on non-Windows systems
- File-by-file publication avoids torn files but cannot guarantee a single coherent generation across separate browser requests; image processing and SQLite updates are not part of the atomic file-swap boundary.
- PowerPoint COM is tied to an interactive Windows user session; packaging must not move rendering into a Session 0 Windows Service
- Windows packaging must bundle the web templates/static assets used by the generated viewer and preserve writable per-user data outside the installation directory
