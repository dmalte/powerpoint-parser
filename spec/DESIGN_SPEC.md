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

## Performance Notes

- Incremental scanning avoids unnecessary rerendering.
- Thumbnails are lazy-loaded with `IntersectionObserver`, so off-screen slide images are not fetched immediately.
- The viewer currently fetches one complete `data/export.json`, parses it into memory, filters/sorts the entire slide array in the browser, and rebuilds the complete matching slide-card DOM on each filter change.
- `renderGrid()` currently calls `slides.indexOf(slide)` for each rendered slide. A 6,000-slide full render therefore performs roughly 18 million element-position checks in addition to DOM creation; this should be removed before larger architectural changes are considered.
- Lazy image loading does not bound DOM size: a 6,000-slide result still creates 6,000 slide cards plus buttons, metadata elements, listeners, and observed `<img>` nodes. This is expected to become the primary browser scalability limit.
- A synthetic 6,000-slide export using the current JSON schema measured approximately 4.7 MB with light text, 12.7 MB with moderate text, and 29.9 MB with heavy extracted text. These are sizing probes rather than browser acceptance measurements; real archives must be benchmarked on representative Windows laptops.
- At the 5,000–6,000 slide target, the preferred optimization order is frontend-first: remove accidental O(n²) work, precompute searchable text/derived deck fields, batch DOM creation, and implement pagination or virtualized/windowed rendering so only a bounded number of slide cards exist at once.
- The current localhost server is a simple single-threaded `HTTPServer`. Because the viewer runs over loopback and thumbnails are lazy-loaded, it is not expected to be the first bottleneck at 6,000 slides, but M007 should measure image-request queuing and consider `ThreadingHTTPServer` plus cache headers as a low-complexity server improvement.
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
- Cross-platform behavior must not accidentally make `pywin32` a required dependency on non-Windows systems
- PowerPoint COM is tied to an interactive Windows user session; packaging must not move rendering into a Session 0 Windows Service
- Windows packaging must bundle the web templates/static assets used by the generated viewer and preserve writable per-user data outside the installation directory
