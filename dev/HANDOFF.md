# Handoff

- Last Updated: 2026-11-14T08:24:05-08:00
- Active Feature: `specs/005-markdown-snippets`

## Current Objective

M009 Markdown visual snippets is completed and deployed on Mac1. The source backend safely renders heading/paragraph sections from opt-in .md files into offline HTML previews and Pillow JPEG cards using existing SQLite/immutable asset generations. Full 161-test suite passed on Pi and Mac1. The native Mac1 source and packaged CLI smoke indexed Markdown/PDF fixtures successfully (4 Markdown snippets plus PDF, then 2 more bundled Markdown snippets). Rebuilt arm64 app preflight 17/17 and ad hoc codesign passed. A verified backup of user YAML/SQLite preceded staged upgrade; existing scan roots, PPTX/PDF types and unpaused preference were preserved, and Markdown remains opt-in. A temporary pause published updated viewer HTML with Markdown checkbox/filter (3,575 decks/18,040 slides/pages at checkpoint), and normal scanning was resumed. The scanner skipped one vanished source without deleting indexed records; separate per-document encrypted/corrupt PDF or PowerPoint conversion failures require future triage. M010 Obsidian-aware double-click vault navigation is a planned separate milestone, not implemented.


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

- M008a: shared image generations stage and validate complete PPTX/PDF slide JPEGs before an atomic per-deck generation-directory rename and SQLite commit. Old image URLs remain intact during updates, deletions and failed SQLite writes. This intentionally retains historical image generations until safe garbage collection is designed.
- M008b: macOS app/CLI/plist upgrades are staged with backups; failed replacement or simulated launchctl bootstrap restores prior binaries. Uninstall is explicit and preserves config/SQLite/images/logs; app/CLI copies retain PyInstaller symlinks. Native installer tests remain pending.
- M008c: scripts/diagnose_macos.py reports local renderer/dependency/config/folder/storage/LaunchAgent readiness with no private paths or telemetry, leaving native Automation/TCC and code signing unverified.
- M008d: scripts/build_macos_fixtures.py creates two PPTX decks (8 slides) covering vector shapes, pictures, tables, charts, Unicode, notes and hidden slides; scripts/compare_slide_images.py compares native render outputs by slide/image dimensions, MAE and visual HTML previews. Pi tests use generated images.
- Added 24 new portable tests for M008a–d: image versions 7, installer lifecycle 7, diagnostics 4, reference/comparison 6. Full repository suite: 132 passing tests. macOS source preflight: 15 pass, one expected native artifact warning.

- Native Mac1 qualification: clean checkout fast-forwarded from Pi commit a31f08b, isolated Python 3.12 environment, all 132 existing tests green.
- Native PyInstaller arm64 app/CLI built successfully, 17/17 artifact/source checks green, codesign --verify --deep --strict passed with ad hoc signing (TeamIdentifier absent).
- Packaged CLI completed real PDF scan, generated JPEG and HTML; packaged .app served /api/status and viewer and accepted /api/shutdown while HOME pointed at an isolated test directory.
- PowerPoint for Mac 16.115 returned -9074 for automated PDF save after trying normal, HFS, delayed activation and Office sandbox staging. AppleScript version query worked. Direct JPG mode appears in PowerPoint.sdef but initial trial timed out. No PPTX images accepted.
- Added path-free opt-in scripts/smoke_macos_powerpoint.py to reproduce error and verify later success. No user LaunchAgent/app installed.

- Full Mac1 regression suite after adding the native smoke harness: 134 passed (six non-failing dependency warnings).

- M008e: Mac user-session two-slide PowerPoint 16.115 export passed in 28.1s and wrote four JPEGs; system MCP-daemon PowerPoint PDF export continued to time out/return -9074. A six-slide complex reference from Terminal wrote five previews and five thumbnails; the excluded sixth slide was intentionally hidden. Native smoke JSON correctly reported status=fail, expected=6, rendered=5.
- M008e: Mac PDF-backed renderer now exposes hidden slides only in its own temporary copied PPTX before export using the existing python-pptx dependency. Original bytes/hidden flags, text and notes stay unchanged, and missing PDF pages still fail safely. New tests cover middle/end hidden slides and original index mappings.
- M008e portable checks: 137 full tests passed on both Pi and Mac1 (three new hidden-slide cases). Mac1 native interactive six-slide smoke now passed after code sync (6/6 in 15.3s).

- M008e native acceptance (Mac1): 6/6 slides, 12 decoded JPEG assets, unchanged original PPTX SHA-256, hidden slide 6 preserved in original and all title/notes mappings verified. 15.3 seconds; no Office error.

- M008f: When agent scanned 3,952 PPTX/PDF files, PowerPoint prompted individually for access to unique temporary paths under archive assets. Mac1 progress was 9/3,952 with 4 errors before stopping. Running app LaunchAgent was booted out; plist was moved from ~/Library/LaunchAgents to a held plist in ~/Library/Application Support/PowerPointVisualArchive; user config/archive preserved.
- M008f: Windows COM remains unchanged. Mac PowerPoint renderer now stages its own per-document private PPTX/PDF inside ~/Library/Containers/com.microsoft.Powerpoint/Data/Documents/PowerPointVisualArchive, where Office has sandbox access. Image rasterization/final publishing remain under archive assets. LibreOffice stays on its own workspace. Existing original/hidden flags and notes remain unchanged.
- M008f Pi: 15 focused renderer tests passed, including sandbox path, cleanup, denial and hidden-slide parity; full repo suite 140 passed. Native Mac acceptance is not yet done.

- M008f Mac1 native isolated test: clean checkout at a159312, arm64 app rebuilt, 17/17 artifact/source checks, ad hoc code signature verified. A dedicated user LaunchAgent ran the rebuilt app with an isolated config containing only two synthetic PPTX fixtures. Both failed with PowerPoint -9074 (0/2 successfully processed), even with Office-container temporary staging. This does not prove the repeated external-file prompts are fixed.
- M008f safe cleanup: temporary acceptance LaunchAgent booted out and its plist removed; production user LaunchAgent remains stopped with startup plist held in Application Support. Production configuration and archive were not edited. No arbitrary source documents were staged for test.

- M008f native retry: User reran 2-slide smoke in signed-in Mac Terminal with sandbox staging: pass 2/2, 4 JPEGs, 0.7 seconds and no Office error. A fresh isolated gui/501 LaunchAgent then passed two reference decks (8 slides, zero errors), and an incremental refresh processed four newly copied synthetic decks (4 OK, 0 errors), for six decks and 24 slides total. The two prior -9074 failures remain recorded: native automation can be intermittent.
- Repeated macOS permission dialogs are not visible to the remote operator. No automatic claim of prompts being resolved; ask the user whether any appeared during six-deck batch.
- After retry verification the temporary acceptance LaunchAgent was booted out and its plist removed; archived synthetic test evidence remains, and the production 3,952-file agent remains disabled with its original plist preserved.

- M008g: User requested browser buttons to stop/resume scanning and make current committed SQLite rows browsable. Pause cooperatively after current PPTX/PDF, persists processing.scan_paused: true, and queues serialized snapshot publication. Resume rediscovers files and skips unchanged already indexed decks; no per-file cursor.
- M008g safety: moved deleted-deck removal to after complete scan; a partial/interrupted run never purges unvisited entries. Existing immutable image generations and old viewer survive failed conversion/publish. API and UI report pausing/paused/building/error.
- M008g Pi: new pause/resume tests cover in-flight cancellation with HTTP partial browse, restart persistence, finish-race snapshot scheduling, deletion safety and config persistence failures. Full suite must be rerun after latest race test.

- M008g Mac1 acceptance: stopped old user scan without deleting SQLite; backed up config/database; persisted scan_paused:true atomically; built partial HTML/JSON from existing 2,959 decks/15,809 slides; upgraded native app with existing installer, 17/17 package preflight and ad hoc codesign verified. Loopback app runs paused, and main viewer/Settings expose Pause & Save and Resume.
- M008g isolated Mac1 test agent on port 8081: initially paused, Scan Now returned HTTP 409; Resume HTTP 202 processed 4/4 PDF fixtures with zero errors; Pause HTTP 202 published/retained current state, and launchctl kickstart preserved paused status/index. Isolated test LaunchAgent removed, production stayed paused. Full Pi+Mac regression suites passed 146/146.
- M008g scanner stop is cooperative after current file; partial DB is preserved and published, deletions are deferred until a completed pass. Resume does incremental change detection rather than a persisted file cursor; it skips unchanged committed documents. User-paused status persists after login.

- M009: Local .md files yield heading-level section snippets with JPEG grid thumbnails plus CSP-protected CommonMark HTML detail previews (raw HTML disabled, no live links or remote resource requests). Section search and local source opening reuse existing Deck/Slide SQLite and immutable generation contracts. No schema migration. Rendered images currently show alt placeholders; local image asset import is future work.
- M010 planned: recognize containing Obsidian vault and open correct vault-relative note/section on double-click; URI/security/fallback must be validated separately. M009 does not silently launch Obsidian.
- Scanner fix: disappeared source path/symlink during os.walk/stat no longer aborts entire refresh. Scan inventory reports skipped missing count; pipeline defers all deletion reconciliation on incomplete pass. Other I/O/permissions failures still abort. This addresses Mac1's reported archive operation error without deleting historical records.
- M009 new small production dependency markdown-it-py (CommonMark structure plus tables, HTML disabled), installed in Pi venv, with explicit native Mac/Windows PyInstaller hidden imports; Pillow already installed.

- M009 native deployment (Mac1): full 161-test suite passed, parser installed in virtualenv, source Markdown/PDF fixture produced 3 decks / 5 records, four HTML previews/JPEG cards and served CSP header. PyInstaller app/CLI built (17/17 preflight; strict codesign passed). Packaged CLI independently indexed another Markdown note (2 sections). Production config/db backed up, native app installed by staged installer; original two roots/PPTX+PDF/unpaused settings unchanged.
- M009 UI: Markdown .md checkbox and type filter published to live 8080 viewer after temporary pause/HTML export; archive snapshot now 3,575 decks/18,040 slides/pages at that checkpoint. Runtime resumed prior unpaused state, Markdown not auto-enabled.
- Mac1 scan recovery: an unavailable file encountered during discovery was safely skipped (skipped_missing=1), no deletion inference; remaining conversion errors (document closed/encrypted, PowerPoint conversion produced no PDF) are distinct issues, not data-loss regressions.
- M010 Obsidian deep-link on double click remains planned; current Markdown Open Original uses OS default file handler.

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
- The shared processing pipeline now publishes immutable whole-deck image versions before SQL promotion. The versions are never overwritten or removed implicitly; disk growth is an accepted reliability trade-off until explicit retention/GC.
- The marker is not a database migration; no-change scans still discover files, but avoid JSON/HTML serialization when the output is complete. Template changes or interrupted publication cause a forced rebuild.
- Guarantee only that each generated JSON/HTML/CSS/JS file is complete. Multi-resource snapshots, in-place image generation and SQLite transactions remain outside M007c.


- Native PowerPoint-for-Mac GUI JPEG export exists, but unattended AppleScript JPEG automation was not established. PDF is only a temporary render intermediate, never archive data.
- Never silently switch to LibreOffice when native conversion fails; fidelity and permission errors must remain visible.
- Do not claim Mac acceptance before osascript, Automation permissions, fonts/fidelity, native signing/Gatekeeper and login run on a Mac.

- On macOS PowerPoint PDF export can skip hidden slides; render the **temporary copy** with those flags cleared, not the user's actual PPTX. Windows COM remains untouched. Do not accept incomplete slide/image sets even if shell output says success.
- The native smoke CLI can exit nonzero with clear status=fail despite producing partial images, and the helper's last printed line does not indicate overall success.

- macOS 14+ may request initial user permission for our ad-hoc-signed app to access PowerPoint's container. This cannot and should not be bypassed. Repeated per-file Office prompts should stop once the Office-native staging path is in use, but must be verified on a small native fixture first.
- Do not restart the large library's LaunchAgent until the bundled renderer is rebuilt, permission handling confirmed, and a bounded user-session smoke test passes.

- M008g: src/ppt_visual_archive/{pipeline,agent,config,server}.py, web/templates/{index,settings}.html.j2, web/static/{js/agent-status.js,js/settings.js,css/style.css,loading.html}, tests/test_pause_resume.py and feature/README/design/requirements docs.
- M009: src/ppt_visual_archive/markdown_processor.py, pipeline.py, scanner.py, agent.py, server.py; web templates/index/settings, web static app/settings/CSS; pyproject.toml, config example, package specs; tests/test_markdown_snippets.py, tests/test_scan_vanished.py; specs/005-markdown-snippets and consolidated docs.
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

- M008a–d code: src/ppt_visual_archive/asset_generations.py, models.py, pipeline.py, packaging/macos/install_agent.py, scripts/preflight_macos_package.py, scripts/diagnose_macos.py, scripts/build_macos_fixtures.py, scripts/compare_slide_images.py.
- M008a–d tests: tests/test_image_generations.py, tests/test_macos_installer_lifecycle.py, tests/test_macos_diagnostics.py, tests/test_macos_reference.py; additional changes in specs/004-macos-desktop-agent, packaging/macos/README.md and consolidated docs.

- scripts/smoke_macos_powerpoint.py and tests/test_macos_native_smoke.py added on Mac1; .gitignore now excludes generated PyInstaller build/ and dist/.

- M008e: src/ppt_visual_archive/mac_renderer.py, tests/test_macos_renderer.py, specs/004-macos-desktop-agent/* plus README, roadmap, design, requirements, changelog and handoff.

- M008f files: src/ppt_visual_archive/mac_renderer.py, tests/test_macos_renderer.py, specs/004-macos-desktop-agent/{spec,plan,tasks}.md, README, ROADMAP, spec/DESIGN_SPEC, spec/REQUIREMENTS, CHANGELOG, dev/HANDOFF.

- M008f native blocker: gui/501 background launch still yields PowerPoint error -9074 for both synthetic reference decks. Need direct signed-in Terminal smoke with new sandbox staging to distinguish file-location permission from background-process automation/TCC identity. Repeated-per-file prompt elimination is unverified; no large scan should resume.

- M008g native Mac rollout pending: rebuild/staged-upgrade app, pause currently running 3,937-file scan, publish current SQLite rows safely, verify viewer output and persisted pause across restart; production should stay paused until the user explicitly clicks Resume.
- M008g implementation and Mac1 acceptance complete; no code blocker. The full production source library is deliberately not fully indexed, and only resumes on explicit user click. Separate M008 visual fidelity, signing/notarization and full-library error triage remain open.
- M009 native Mac1 validation and data-preserving app upgrade are pending; installed PowerPoint Archive may still run an older renderer until updated. The Mac1 archive currently has 2,959 decks/15,809 slides published and reported a vanished source file on Nov 14; new scanner fallback needs native verification. Do not enable .md in user settings without explicit action.
- Markdown MVP images are rendered as alt-text placeholders; no Obsidian wikilinks or vault deep-link opening yet (M010).
- M009 source/native acceptance and app upgrade complete. No outstanding Markdown backend implementation blocker. Markdown file type disabled in user config by default until manually opted in.
- Mac1 existing PPTX/PDF library continues incremental scan with per-file processing failures; one inaccessible file is skipped and deletion reconciliation deferred. Some documents may be closed/encrypted, others fail PowerPoint PDF export. Error diagnostics/triage remain a separate task.
- M010 planned: detect Obsidian .obsidian vault root and open vault note/section from Markdown double click with URI escaping, trusted vault names and fallback; not implemented in M009.
## Open Issues

- M004 installer/PPTX/logon smoke validation remains pending.
- M005 packaged Windows tray/menu smoke validation remains pending.
- M007 representative Edge/Chrome timing, scroll smoothness, and memory measurements on a company-class Windows laptop remain pending.
- Frontend report measures browser-observable gaps, not a guaranteed sustained FPS. Firefox may not expose JS heap; handle null metrics explicitly.
- The packaged Windows installer with the newly added performance files has not been built or smoke-tested.
- M007c replaces generated files atomically per path, but does not provide a single transactional view across multiple HTTP requests, SQLite updates or changed/deleted thumbnails. Real PPTX/Windows acceptance remains pending.
- Windows/Mac startup, real PPTX rendering, image loading, and 20,000-slide device-specific measurements still require representative platform runs.
- Generation-specific asset paths eliminate in-place overwrites; a process crash between directory rename and SQLite commit may leave an orphan version. Safe garbage collection and abrupt power-loss durability remain separate work.

- M008: Mac user-session conversion is proven for both simple and complex decks including the hidden sixth slide. Per-user LaunchAgent Automation permission, real app installation/upgrade and Windows/Mac pixel/font-layout fidelity remain pending.
- M008 installer upgrade, rollback and uninstall behavior are validated with Pi-based fault injection, but native launchctl/signing/notarization, actual Mac PowerPoint and system permissions are unverified.
- M004/M005 Windows installer/COM/logon/tray and M007 real image/browser benchmarks remain pending.

- PowerPoint-for-Mac export works from the unlocked user Terminal for 2/2 and 6/6 slides; M008e fixes hidden-slide omission. Daemon-context AppleScript continues to be unreliable, so PPTX rendering should run in the interactive user-session agent.
- Native user-level LaunchAgent install/upgrade/login and actual PPTX visual fidelity are not yet accepted. Do not auto-install or sign/notarize until renderer is validated.

## Next Step

M009 complete. Commit native acceptance docs and fast-forward clean Mac1 checkout. User can enable Markdown in http://127.0.0.1:8080/settings.html by checking Markdown and selecting folders, then Scan Now; existing user config is preserved until they opt in. Future M010: Obsidian-aware vault navigation. Also triage failed encrypted/PDF/PowerPoint source conversions in a separate maintenance task. Do not push the local development repo without authorization.

- M009 Mac1: 161/161 tests pass; native PyInstaller app/CLI 17/17 checks and ad hoc strict signature verification; packaged Markdown CLI processed a new Markdown note (2 snippets), source native mixed Markdown/PDF library 3 decks/5 records with CSP HTML and JPEGs; production app upgraded with config/DB backup, MD controls published, no automatic MD opt-in, prior scan preference restored. Pi suite 161/161, Mac/Windows static packaging preflights pass.
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
- M008a–d portable tests: 24 new checks passed (7 image generations, 7 installer lifecycle, 4 readiness diagnostics, 6 reference/image comparison).
- M008a–d full tests: 132 passed (2026-11-12); packaging source preflight 15 passed, one warning (Mac app binary not built on Pi).
- Reference PPTX fixture run: 2 decks, 8 slides; hidden-slide flag and notes validated with python-pptx. Image comparator verified with generated JPEGs.
- Native Mac1: Python 3.12; 132/132 portable tests; PyInstaller arm64 app/CLI built; 17/17 source/binary checks; ad hoc codesign verified.
- Native bundled CLI real PDF scan/build and isolated packaged agent HTTP startup/shutdown passed. Native macOS readiness: 10 pass, 2 warnings (not installed), 3 unverified.
- PowerPoint 16.115 AppleScript PDF export failed -9074 on multiple path/activation trials. Direct JPG mode enumerated but output not verified; TCC/fidelity pending.
- M008 native PowerPoint/AppleScript, bundle, TCC and LoginAgent: NOT RUN.

- Real Windows browser performance acceptance: not run on this host.
