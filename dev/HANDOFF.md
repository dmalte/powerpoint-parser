# Handoff

- Last Updated: 2026-11-12
- Active Feature: `specs/003-large-archive-performance`

## Current Objective

Complete M007 / REQ-PERF-001 real Windows performance acceptance for at least 6,000 slides/pages. Browser and backend performance hooks are now integrated; M004/M005 packaged Windows acceptance remains pending.

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

## Decisions

- Keep SQLite and the single local export for the 6,000-slide target unless real browser measurements show the data payload remains a material bottleneck after DOM/search optimization.
- Bound the live grid DOM to at most 240 slide cards.
- Preserve full filtered-result search/sort/group semantics and full-result modal navigation.
- Use cache revalidation rather than immutable caching because generated image paths can be reused after a rebuild.
- Do not claim real Edge/Chrome latency or memory acceptance before representative Windows hardware is benchmarked.
- Performance records intentionally contain no search terms, paths, filenames, or slide content; browser records are in memory until explicitly downloaded and backend records stay in per-user logs.
- Report latest 20 backend runs through loopback-only HTTP; preserve static file viewing without a backend metrics endpoint.

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
- `dev/HANDOFF.md`

## Open Issues

- M004 installer/PPTX/logon smoke validation remains pending.
- M005 packaged Windows tray/menu smoke validation remains pending.
- M007 representative Edge/Chrome timing, scroll smoothness, and memory measurements on a company-class Windows laptop remain pending.
- Frontend report measures browser-observable gaps, not a guaranteed sustained FPS. Firefox may not expose JS heap; handle null metrics explicitly.
- The packaged Windows installer with the newly added performance files has not been built or smoke-tested.

## Next Step

Benchmark the 6,000-slide viewer in Edge and Chrome on representative Windows hardware, download its report, compare latency and memory with explicit release budgets, and optimize confirmed bottlenecks. Separately perform M004 installer/PPTX/logon and M005 tray smoke validation on Windows. Rebuild the Windows installer to include new performance assets.

## Validation

- `python scripts/workflow_gate.py pre-implement --change-class feature` → passed for `specs/003-large-archive-performance`.
- `.venv/bin/python -m pytest tests/test_large_archive_performance.py -q` → 4 passed.
- `.venv/bin/python scripts/benchmark_large_archive.py --slides 6000 --text-chars 1000` → `slides=6000 decks=200 json_mib=12.83`.
- `.venv/bin/python -m pytest tests -q` → 61 passed (2026-11-12).
- `.venv/bin/python -m pytest tests/test_performance_instrumentation.py -q` → 6 passed.
- Synthetic 6,000-slide headless Chromium on Raspberry Pi: initial DOM grid 240 cards, search returned one matching slide, zero JS errors, and downloaded JSON included `scan` and `build` backend records. Example Pi smoke measurements: ~591 ms initial readiness, ~28 ms query filtering; NOT Windows benchmarks.
- Real Windows browser performance acceptance: not run on this host.
