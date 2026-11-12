# Handoff

- Last Updated: 2026-11-12T14:27:05-08:00
- Active Feature: `specs/004-macos-desktop-agent`

## Current Objective

M008 macOS source implementation is prepared and validated on Raspberry Pi. Actual PowerPoint-for-Mac AppleScript execution, Automation consent and native app packaging/login acceptance remain pending. M004/M005 Windows packaged acceptance remains pending.

## Completed

- M005 self-service controls checkpoint committed as `2021893`; portable/full tests were green (51 passed).
- Created/selected `specs/003-large-archive-performance` and passed the feature pre-implementation gate.
- Added one-time deck/slide normalization and cached scoped lowercased search blobs.
- Removed the per-card `slides.indexOf(slide)` O(n²) render hotspot.
- Added fixed 240-card grid pagination with Previous/Next/range display while preserving modal navigation over all filtered results.
- Batched each grid page through `DocumentFragment`.
- Added revalidation cache headers for generated deck images and now no-store for export.json; API responses remain no-store.
- Added deterministic `scripts/benchmark_large_archive.py` and focused performance regression tests.
- A 6,000-slide / 200-deck fixture with 1,000 text characters per slide produces 12.83 MiB JSON.
- Added browser performance metrics for fetch, body reading, JSON parse, normalization, initial interaction, search/filter, sort, grid rendering, image load, modal opening, scrolling, long tasks, and optional JS heap.
- Added a **Performance** topbar panel with p50/p95/max, bounded samples, a clear button and an explicit downloadable path-free JSON report. Reports include recent backend runs if served by the local app.
- Added aggregate backend scan/build timing stages, a per-user `performance.jsonl` log, and loopback-only `GET /api/performance`.
- Headless Chromium on Raspberry Pi successfully loaded the synthetic 6,000-slide archive (240 cards), searched down to one result, opened a preview, and downloaded a report containing scan/build records with no JS errors.
- M007a: Added `scripts/benchmark_viewer.py` and `scripts/measure_viewer.mjs` for revision-tagged headless Chromium/CDP workloads. Measured 6,000 and 20,000 synthetic slides with 1,000-character bodies and retained a 240-card DOM bound. Reports are generated under ignored `.runtime/benchmarks/`.
- M007b: Queued first scan asynchronously, made localhost serving immediate, added a first-run loading page that polls progress, and made /api/status expose sanitized numeric phase/completed/total/errors while keeping the old viewer active during refresh. Settings and the viewer's top bar show progress; failures remain visible while server runs.
- Added portable real-PDF progress/API/error/first-run tests and Chromium CDP benchmark integration tests.
- M007c: Agent skips expensive viewer builds after an unchanged scan when a source/config fingerprint and completion marker confirm the existing generated site is intact; reports viewer_rebuilt in last_summary.
- M007c: Builder stages export JSON, HTML, CSS and JS away from live paths; os.replace swaps intact files, index page goes last for initial publication, and a last-written marker forces repair after an interrupted publish.
- M007c: Built-in HTTP streams an open JSON file and uses no-store, avoiding stale same-second 304 responses. Browser fetch likewise bypasses the cache.
- Added eight M007c regression tests for first publication order, unchanged/changed/deleted scans, stale/missing artifacts, staging/publish failure recovery, conditional HTTP caching and concurrent readers.
- M007d added scripts/benchmark_history.py, a small example threshold file, and six regression tests; outputs are local offline HTML history and JSON comparisons. Clean compatible revisions are required for automatic warnings.
- M007d clean-revision comparison e0958de vs c685153 completed for 6,000 and 20,000 slides on Pi: 2 comparable scenarios, 0 warning metrics using example thresholds.
- M007e strict scanner rejects missing/inaccessible scan roots, traversal/stat failures before any deletion inference, protecting prior indexed data.
- M007e invalid PDFs no longer replace existing slide sets; IndexDB replace_deck_and_slides commits changed metadata and slides in one transaction, rolling back on failures.
- M007e .viewer-build marker v2 includes a digest of active SQLite deck signatures and slide counts so a scan that committed but crashed before export will force recovery on restart without a DB schema migration.
- Added tests/test_recovery.py (7 tests): mount failure, walk/stat error, corrupt PDF retry, transaction rollback, crash after SQLite commit, and simulated ENOSPC publication.
- M004a: added portable packaging source and optional PE header checks, build.ps1 fail-fast validation, local JSON reporting, and five preflight regression tests. 14 static checks passed; Windows artifacts absent (warning, not acceptance).
- M007f: cached repeated locale-formatted dates and disconnected stale lazy-image observers before each grid redraw. Added focused regression coverage; benchmarked 50,000 synthetic slides (~106 MiB JSON, ~237–239 MB JS heap, ~1.8–2.1 s initial readiness on Pi).
- M007f clean-revision comparison 7cc0da7 → 03fc5f4: 6K grid p95 126.7 → 102.5 ms, filter-to-grid p95 136.8 → 110.9 ms, startup 963 → 849 ms; 20K grid p95 146.6 → 67.5 ms, filter-to-grid p95 209.5 → 158.9 ms, startup 1,425 → 1,225 ms. Both had zero warning metrics under example thresholds.


- M008: platform-based PPTX renderer factory, Windows COM unchanged; macOS default AppleScript exports only a temporary PDF and PyMuPDF makes normal JPEG/PNG files. Original PPTX text and notes go to SQLite/JSON; no PDF persists.
- M008: optional LibreOffice backend is explicitly selected, not automatic; source paths are argv, not interpolated into scripts or passed through shell. The Mac automation opens a temporary copy to avoid closing a user's already-open original PPTX; raw stderr is logged locally, not returned through /api/status.
- M008: Application Support/Logs paths, Finder open/reveal/open-logs, and PyInstaller .app + user LaunchAgent source scaffold. No Mac changes performed.
- M008: 15 focused portable tests passed; source preflight 14 pass / 1 warning (no Mac binary); full Pi suite 108 passed.

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
- Fail an incomplete scan rather than interpreting unreadable roots/files as deletions; existing index survives until the next successful retry.
- Keep thumbnail files outside the SQL transaction. Renderer writes to existing asset paths remain a known risk, requiring a separate versioned-media design if observed.
- The marker is not a database migration; no-change scans still discover files, but avoid JSON/HTML serialization when the output is complete. Template changes or interrupted publication cause a forced rebuild.
- Guarantee only that each generated JSON/HTML/CSS/JS file is complete. Multi-resource snapshots, in-place image generation and SQLite transactions remain outside M007c.


- Native PowerPoint-for-Mac GUI JPEG export exists, but unattended AppleScript JPEG automation was not established. PDF is only a temporary render intermediate, never archive data.
- Never silently switch to LibreOffice when native conversion fails; fidelity and permission errors must remain visible.
- Do not claim Mac acceptance before osascript, Automation permissions, fonts/fidelity, native signing/Gatekeeper and login run on a Mac.

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
- src/ppt_visual_archive/pipeline.py, src/ppt_visual_archive/builder.py stage timings and M007c staged atomic publishing
- `scripts/benchmark_viewer.py`, `scripts/measure_viewer.mjs`, `tests/test_browser_benchmark.py`
- `src/ppt_visual_archive/agent.py`, `web/static/loading.html`, `web/static/js/agent-status.js`
- `tests/test_background_startup.py`, `tests/test_agent_runtime.py`, `web/static/js/settings.js`
- web/templates/settings.html.j2, .gitignore
- M007c: src/ppt_visual_archive/agent.py, src/ppt_visual_archive/server.py, web/static/js/app.js, web/static/js/agent-status.js, tests/test_incremental_publishing.py
- M007d: scripts/benchmark_history.py, config/performance_thresholds.example.json, tests/test_benchmark_history.py
- M007e: src/ppt_visual_archive/scanner.py, src/ppt_visual_archive/pipeline.py, src/ppt_visual_archive/index_db.py, src/ppt_visual_archive/builder.py, tests/test_recovery.py
- M004a: packaging/windows/build.ps1, scripts/preflight_windows_package.py, tests/test_windows_preflight.py, packaging/windows/README.md, specs/001-windows-desktop-agent/{spec,plan,tasks}.md

- `dev/HANDOFF.md`

- M008: src/ppt_visual_archive/mac_renderer.py, renderer_factory.py, pipeline.py, config.py, platform_paths.py, agent.py, server.py, config/config.example.yaml.
- M008: packaging/macos/PowerPointVisualArchive.spec, build.sh, install_agent.py, README.md, scripts/preflight_macos_package.py, tests/test_macos_renderer.py, tests/test_macos_packaging.py.
- M008: specs/004-macos-desktop-agent, PROJECT_WORKFLOW.json and consolidated project docs.

## Open Issues

- M004 installer/PPTX/logon smoke validation remains pending.
- M005 packaged Windows tray/menu smoke validation remains pending.
- M007 representative Edge/Chrome timing, scroll smoothness, and memory measurements on a company-class Windows laptop remain pending.
- Frontend report measures browser-observable gaps, not a guaranteed sustained FPS. Firefox may not expose JS heap; handle null metrics explicitly.
- The packaged Windows installer with the newly added performance files has not been built or smoke-tested.
- M007c replaces generated files atomically per path, but does not provide a single transactional view across multiple HTTP requests, SQLite updates or changed/deleted thumbnails. Real PPTX/Windows acceptance remains pending.
- Windows/Mac startup, real PPTX rendering, image loading, and 20,000-slide device-specific measurements still require representative platform runs.
- Image assets are not versioned; renderers can update on-disk files before SQL commit. True cross-media atomicity and abrupt power-loss durability are outside the current increment.

- M008 native PowerPoint/osascript PDF conversion is unverified. Automation consent, PDF page parity and font/layout fidelity, actual .app build and login/LaunchAgent, and Finder actions remain pending.
- M008 is only a developer install scaffold: signing/notarization, upgrades/uninstall and transactional image publishing are not proven.
- M004/M005 Windows installer/COM/logon/tray and M007 real image/browser benchmarks remain pending.

## Next Step

M008 next: run a native Mac smoke test with a real PPTX to verify AppleScript, Automation permission, images and app login. Only after acceptance mark M008 done. M004/M005 Windows checks and M007 real-library benchmarks remain separate.

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
- M007c: eight focused tests verify no-change skip, changed/deleted PDF, source/asset invalidation, staging/publish failures, HTTP concurrent readers, first-install ordering and stale validator prevention; all passed on Pi.
- M007c one-page PDF example: initial refresh ~440 ms; unchanged scans ~5.5 ms, 5.2 ms, 5.1 ms, with log operations scan+build then scan only. Not a representative large-library or Windows benchmark.
- Full regression suite after M007c: 74 passed (2026-11-12); JavaScript syntax checks and Git diff checks passed.
- M007d focused tests: 6 passed; 7 saved Pi runs yielded 2 clean comparable cases (6K and 20K) with zero warning metrics using example thresholds.
- M007e focused failure-injection tests: 7 passed. Full repository suite: 87 passed (2026-11-12).
- M004a: 14 static source checks passed, Windows-generated PE artifacts not supplied; five preflight tests passed. Full suite after M004a: 92 passed.
- M007f: clean-revision 6K/20K Pi benchmarks (7cc0da7 vs 03fc5f4) completed with zero warnings. 50K synthetic stress passed with 240-card limit and 106 MiB JSON; JavaScript heap about 239 MB.
- Full portable suite after M007f: 93 passed (2026-11-12). JS syntax and Git whitespace checks passed.
- M008 focused renderer/packaging tests: 15 passed on Pi.
- M008 packaging source preflight: 14 pass, zero fail, one expected warning (no native Mac artifacts).
- Full repository tests after M008: 108 passed (2026-11-12).
- Native Mac PowerPoint/AppleScript, bundled app and login acceptance: NOT RUN.
- Real Windows browser performance acceptance: not run on this host.
