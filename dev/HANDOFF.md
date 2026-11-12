# Handoff

- Last Updated: 2026-11-12T13:12:24-08:00
- Active Feature: `specs/003-large-archive-performance`

## Current Objective

Complete M007 / REQ-PERF-001 real Windows performance acceptance for at least 6,000 slides/pages. M007a repeatable browser baselines and M007b non-blocking startup/progress are implemented. M004/M005 packaged Windows acceptance remains pending.

## Completed

- M005 self-service controls checkpoint committed as `2021893`; portable/full tests were green (51 passed).
- Created/selected `specs/003-large-archive-performance` and passed the feature pre-implementation gate.
- Added one-time deck/slide normalization and cached scoped lowercased search blobs.
- Removed the per-card `slides.indexOf(slide)` O(n²) render hotspot.
- Added fixed 240-card grid pagination with Previous/Next/range display while preserving modal navigation over all filtered results.
- Batched each grid page through `DocumentFragment`.
- Added revalidation cache headers for generated deck images and `no-cache` for `export.json`; API responses remain `no-store`.
- Added deterministic `scripts/benchmark_large_archive.py` and focused performance regression tests.
- A 6,000-slide / 200-deck fixture with 1,000 text characters per slide produces 12.83 MiB JSON.
- Added browser performance metrics for fetch, body reading, JSON parse, normalization, initial interaction, search/filter, sort, grid rendering, image load, modal opening, scrolling, long tasks, and optional JS heap.
- Added a **Performance** topbar panel with p50/p95/max, bounded samples, a clear button and an explicit downloadable path-free JSON report. Reports include recent backend runs if served by the local app.
- Added aggregate backend scan/build timing stages, a per-user `performance.jsonl` log, and loopback-only `GET /api/performance`.
- Headless Chromium on Raspberry Pi successfully loaded the synthetic 6,000-slide archive (240 cards), searched down to one result, opened a preview, and downloaded a report containing scan/build records with no JS errors.
- M007a: Added `scripts/benchmark_viewer.py` and `scripts/measure_viewer.mjs` for revision-tagged headless Chromium/CDP workloads. Measured 6,000 and 20,000 synthetic slides with 1,000-character bodies and retained a 240-card DOM bound. Reports are generated under ignored `.runtime/benchmarks/`.
- M007b: Queued first scan asynchronously, made localhost serving immediate, added a first-run loading page that polls progress, and made /api/status expose sanitized numeric phase/completed/total/errors while keeping the old viewer active during refresh. Settings and the viewer's top bar show progress; failures remain visible while server runs.
- Added portable real-PDF progress/API/error/first-run tests and Chromium CDP benchmark integration tests.

## Decisions

- Keep SQLite and the single local export for the 6,000-slide target unless real browser measurements show the data payload remains a material bottleneck after DOM/search optimization.
- Bound the live grid DOM to at most 240 slide cards.
- Preserve full filtered-result search/sort/group semantics and full-result modal navigation.
- Use cache revalidation rather than immutable caching because generated image paths can be reused after a rebuild.
- Do not claim real Edge/Chrome latency or memory acceptance before representative Windows hardware is benchmarked.
- Performance records intentionally contain no search terms, paths, filenames, or slide content; browser records are in memory until explicitly downloaded and backend records stay in per-user logs.
- Report latest 20 backend runs through loopback-only HTTP; preserve static file viewing without a backend metrics endpoint.
- Keep benchmark fixtures deterministic but treat their shared JPEGs and Pi Chromium latency as synthetic frontend regression evidence, not PowerPoint/Windows performance acceptance.
- Keep the initial processing worker asynchronous and serialized with all other refresh actions. An indexed archive stays accessible while updating; initial missing-index loads show a status page.

## Files Changed

- `ROADMAP.md`
- `spec/REQUIREMENTS.md`
- `spec/DESIGN_SPEC.md`
- `README.md`
- `CHANGELOG.md`
- `specs/003-large-archive-performance/*`
- `web/static/js/app.js`
- `web/static/css/style.css`
- `web/templates/index.html.j2`
- `src/ppt_visual_archive/server.py`
- `src/ppt_visual_archive/perf_metrics.py`
- `tests/test_performance_instrumentation.py`
- `web/static/js/performance.js`
- `src/ppt_visual_archive/pipeline.py`, `src/ppt_visual_archive/builder.py` stage timings
- `scripts/benchmark_viewer.py`, `scripts/measure_viewer.mjs`, `tests/test_browser_benchmark.py`
- `src/ppt_visual_archive/agent.py`, `web/static/loading.html`, `web/static/js/agent-status.js`
- `tests/test_background_startup.py`, `tests/test_agent_runtime.py`, `web/static/js/settings.js`
- `web/templates/settings.html.j2`, `.gitignore`
- `dev/HANDOFF.md`

## Open Issues

- M004 installer/PPTX/logon smoke validation remains pending.
- M005 packaged Windows tray/menu smoke validation remains pending.
- M007 representative Edge/Chrome timing, scroll smoothness, and memory measurements on a company-class Windows laptop remain pending.
- Frontend report measures browser-observable gaps, not a guaranteed sustained FPS. Firefox may not expose JS heap; handle null metrics explicitly.
- The packaged Windows installer with the newly added performance files has not been built or smoke-tested.
- Incremental static viewer rebuilds are still non-atomic and occur even when unchanged; M007c is a separate proposed follow-on.
- Windows/Mac startup, real PPTX rendering, image loading, and 20,000-slide device-specific measurements still require representative platform runs.

## Next Step

Use the new repeatable 6,000/20,000-slide benchmark on Windows/Chrome/Edge and on Mac for cross-platform comparisons; collect reports from real archives to size thumbnail and processing bottlenecks. Select M007c (skip unchanged rebuilds and atomic static publishing) separately if requested. Complete M004 installer/PPTX/logon and M005 tray smoke validation on Windows; rebuild the installer to include new assets.

## Validation

- `python scripts/workflow_gate.py pre-implement --change-class feature` → passed for `specs/003-large-archive-performance`.
- `.venv/bin/python -m pytest tests/test_large_archive_performance.py -q` → 4 passed.
- `.venv/bin/python scripts/benchmark_large_archive.py --slides 6000 --text-chars 1000` → `slides=6000 decks=200 json_mib=12.83`.
- `.venv/bin/python -m pytest tests -q` → 61 passed (2026-11-12).
- `.venv/bin/python -m pytest tests/test_performance_instrumentation.py -q` → 6 passed.
- Synthetic 6,000-slide headless Chromium on Raspberry Pi: initial DOM grid 240 cards, search returned one matching slide, zero JS errors, and downloaded JSON included `scan` and `build` backend records. Example Pi smoke measurements: ~591 ms initial readiness, ~28 ms query filtering; NOT Windows benchmarks.
- M007a benchmark: 6,000 slides, 953 ms initial readiness, 131 ms p95 filter-to-grid; 20,000 slides, 1,377 ms initial readiness, 195 ms p95 filter-to-grid (Pi headless Chromium, 1,000 synthetic text characters per slide, placeholders, 240-card bound).
- M007b tests: first-run HTTP responds with live status before slow refresh finishes; completion loads actual viewer, errors stay visible, and a real PDF scan emits source-free progress records.
- `.venv/bin/python -m pytest tests -q` → 66 passed (2026-11-12); Node JS syntax checks and `git diff --check` passed.
- Real Windows browser performance acceptance: not run on this host.
