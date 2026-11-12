# Implementation Plan: Large Archive Viewer Performance

- Feature: `specs/003-large-archive-performance`
- Milestone: M007
- Requirements: REQ-PERF-001

## Current Context

The viewer loads one complete `export.json`, filters/sorts in memory, and currently rebuilds a card subtree for every match. A 6,000-slide full result creates 6,000 cards despite lazy image loading, and `renderGrid()` calls `slides.indexOf(slide)` per card. The loopback server is now threaded from M005.

## Approach

Optimize frontend work before changing the backend architecture:

1. Normalize deck/slide derived fields once after JSON load (file type, lowercased search fields, stable full-result index).
2. Cache combined search blobs by active scope signature so repeated text queries do not repeatedly lowercase/join every source field.
3. Paginate the rendered grid at a fixed 240-card maximum; filtering still computes the full result set, modal navigation still uses the full filtered array.
4. Use `DocumentFragment` for each page render and reset page index on filter/sort/group changes.
5. Add cache-control for generated deck image assets while keeping control/data responses uncached.
6. Add a deterministic 6,000-slide fixture generator and structural regression checks.

## Components and Responsibilities

- `web/static/js/app.js`: normalization, search caching, pagination, bounded grid rendering.
- `web/templates/index.html.j2`: pagination controls/range display.
- `web/static/css/style.css`: pagination layout.
- `server.py`: static image cache policy; existing threaded loopback server retained.
- `scripts/benchmark_large_archive.py`: deterministic synthetic export generator/sizing tool.
- `tests/test_large_archive_performance.py`: structural and server-cache regression tests.

## Data Flow and Persistence

No persisted schema changes. Runtime-only properties prefixed with `_` are added to parsed JS objects after load and are never written back. The full export remains in memory for current-scale search semantics.

## Compatibility and Risk

- Client-side pagination must not change filtered result semantics or modal navigation.
- Group headers may repeat across page boundaries; this is acceptable and preferable to unbounded DOM creation.
- Star toggles can reorder a starred sort and therefore reset the visible grid page through the existing filter/render path.
- Cache headers are limited to generated deck image assets; `export.json`, HTML, JS/CSS, and `/api/*` remain revalidated/no-store as appropriate.
- Real browser latency/memory cannot be validated on this host and remains a manual benchmark item.

## Validation

- Source-level regression checks for page bound, removal of `indexOf`, pagination controls, and normalization/cache helpers.
- Server HTTP test for immutable image cache header and no-store API behavior.
- Execute benchmark generator for exactly 6,000 slides and record resulting size.
- Full pytest suite.
- Later Chrome/Edge benchmark on representative company Windows laptop.

## Local Diagnostics and Measurement Plan (2026-11-12)

- A small browser helper loaded before `app.js` captures navigation timing and bounded operation durations for fetch/parse/init, filter/sort/grid/pagination, thumbnails, preview, scroll frame gaps, and supported long tasks/memory. Record only numeric timings/counters; never persist search terms or file names.
- A top-bar Performance panel summarizes measurements and downloads an explicitly requested JSON report. It requests recent backend metrics via a loopback-only `GET /api/performance`; opening the viewer as `file://` still exports browser measurements without backend data.
- Backend `TimedRun` records aggregate durations and counts around scan discovery, change detection, PPTX/PDF processing, DB updates, and viewer export. Append JSONL to per-user application log directory. Provide a bounded last-20 event endpoint; never serve logs containing paths.
- Export data and SQLite schemas stay untouched. No telemetry leaves the user's machine automatically. Measure cost should be bounded; do not add dependencies or always-on high-frequency sampling.
- Structural and runtime tests verify the report's privacy boundary, stage timings, API response, and generated viewer asset. Browser smoke tests are useful but do not substitute for Windows acceptance numbers.

## Automated Browser Benchmark and Nonblocking Agent (2026-11-12)

- A Python driver prepares real generated viewer HTML/JS plus synthetic JSON from the existing fixture generator, then invokes a Node.js built-in-WebSocket Chrome DevTools Protocol harness against a loopback HTTP server. It exercises search, sorting/grouping, pagination, and modal interactions at 6,000 and 20,000 slides; records the in-app performance report, DOM bound and CDP heap/DOM metrics, alongside Git revision and browser version. No npm package or production dependency is required. Synthetic thumbnails are placeholders; real image/Office performance must be measured separately.
- Agent startup creates the output directory, queues an initial refresh on its existing single-refresh worker, starts the server and scheduler immediately, and continues serving a previous archive while a refresh is running. If no index.html exists, the HTTP server shows a small loading page that polls /api/status and reloads after the first build. Errors remain observable without terminating the server.
- Pipeline emits progress callback records for discovery, change detection, document processing and build; the existing runtime serializes them and exposes a path-free progress object in /api/status. Settings and viewer surfaces show the counts/phases. Injected test refresh functions retain their existing single-config call contract.
- No PPTX COM change, macOS renderer, install/startup change, cloud telemetry, persisted schema migration, or server-side search is introduced. Validate async correctness, error recovery and API progress with deterministic tests, and benchmark on Pi as functional evidence only.


## Documentation Convergence

Update design/requirements/roadmap/README/changelog/handoff with implemented optimizations and clearly distinguish portable validation from pending real-browser measurements.

## M007c — Incremental Freshness and Atomic File Swap (2026-11-12)

- agent.refresh_archive checks scan results and builder.viewer_is_current(config). A no-change scan skips build_viewer only if a persisted output marker matches the current web asset fingerprints and expected output files. It reports a boolean rebuild decision in the refresh summary; API status remains backward compatible.
- builder.build_viewer generates data/export.json, HTML templates, and static CSS/JS under a sibling staging directory on the same output volume, with no live file writes during generation. Publish using os.replace per file; retain existing static directories rather than deleting them. No external dependencies.
- Store a private .viewer-build.json marker after successful publication with schema version, source/config fingerprint and expected published file sizes/mtime. Invalidate the marker immediately before the first live file swap. A failure during staging preserves the full previous publication; a failure during publication forces retry next refresh. Stage directory cleanup is automatic.
- Swap static CSS/JS first, settings next, JSON next, and index.html last so a new installation never exposes the viewer entrypoint before the data is readable. The export endpoint opens a stable file descriptor and ignores coarse If-Modified-Since validators; both server and JavaScript use no-store semantics.
- Content-level atomicity is per file. A full-page browser load racing a multi-file publication can still combine different complete generations; image exports are still modified by their processors. No claim of multi-file ACID semantics.
- Acceptance covers first run, repeat no-op refresh, actual changes/deletion, changed title/assets, missing asset, exception before/after publish, live threaded HTTP reading of large exports, and regression against current CLI/agent tests.

## M007d — Dashboard and Comparison Engine (2026-11-12)

- Add an stdlib-only reporter over the existing .runtime/benchmarks JSON schema; preserve generated reports outside Git. Match environment including exact browser build and input shape to avoid false cross-device comparisons. A dirty or legacy unknown-worktree baseline must not become the automatic reference.
- Emit offline, escaped HTML with sortable chronological results and per-size sparklines, plus a JSON comparison suitable for automation. Default policy reports warnings at configurable per-metric percentage thresholds; optional explicit fail-on-warning is intended only for stable CI environments.
- Use deterministic synthetic reports in regression tests for mismatch, missing metric, insufficient sample count and a genuine warning; run it against the existing Pi reports as an integration check.
