# Large Archive Viewer Performance

- Feature: `specs/003-large-archive-performance`
- Workflow: agent-managed
- Status: active
- Milestone: M007
- Requirements: REQ-PERF-001

## Objective

Make the local browser remain responsive with at least 6,000 indexed slides/pages without replacing the local-first SQLite/static-export architecture prematurely.

## Scope

### In Scope

- Reproducible synthetic 6,000-slide benchmark/export fixture.
- Remove avoidable O(n²) browser work and cache derived deck/search fields.
- Bound slide-card DOM size with client-side pagination while preserving full filtered-result modal navigation.
- Keep lazy thumbnail loading and make pagination reset correctly after filtering/sorting/grouping changes.
- Threaded loopback static serving and cache-friendly revalidation headers for generated image assets.
- Portable structural/performance regression tests plus documented real-browser benchmark procedure.
- Local, opt-in-to-export performance diagnostics: browser navigation/data load/parse/init/search/sort/grid/modal/thumbnail/scroll observations, plus scan, document processing, and static export timing.
- A path- and content-free JSON report downloadable from the viewer; backend metrics available locally without cloud upload.
- Deterministic browser performance benchmarking at 6,000 and 20,000 slides with scripted user interactions, bounded DOM checks, and locally saved revision-labelled reports (synthetic image/load limitations clearly marked).
- Start the agent's localhost viewer before initial indexing finishes; serve a progress/ready page when no index exists, keep an existing viewer usable, and expose anonymized scan/build progress in the status API and UI.

### Out of Scope

- Cloud/server deployment, remote database, Elasticsearch, semantic search, or multi-user backend.
- Server-side query/pagination API unless measurements after these optimizations justify it.
- Claiming real Windows-browser latency budgets have passed before representative hardware testing.

## Required Behavior

1. A full 6,000-slide result must not create 6,000 slide cards in the DOM at once.
2. The grid renders a fixed page of at most 240 slide cards and exposes Previous/Next navigation plus the current result range.
3. Modal navigation continues across the full filtered result set, not only the visible page.
4. Filtering avoids repeated filename-extension derivation and whole search-haystack normalization where the search-scope combination has not changed.
5. Rendering must not call `slides.indexOf(slide)` per card.
6. Filter/sort/group changes reset to the first valid page and never leave an empty page while results exist.
7. The local server remains loopback-only, handles concurrent image requests, and may cache generated deck image assets without caching control APIs.
8. A benchmark fixture can generate representative 6,000-slide JSON payloads for browser/manual measurement.
9. The viewer records bounded in-memory timing samples from real interactions and offers a local JSON download, identifying unavailable browser APIs rather than fabricating numbers.
10. Scan/build work records aggregate stage durations/counts locally; no filenames, source paths, search terms, slide content, or archive data are included in diagnostics.
11. The viewer can include the most recent local backend performance runs when served through its loopback server; file:// mode remains useful without the API.
12. A headless-browser benchmark can load synthetic 6,000/20,000-slide archives, exercise filtering, sorting, pagination and modal opening, assert a bounded DOM, and save structured reports with Git revision and browser information. Measurements remain environment-specific and do not claim Windows acceptance.
13. The per-user agent starts its HTTP viewer promptly while its first scan/build runs in a worker. When no archive exists, a startup page polls a path-free progress endpoint until the viewer is ready or the build fails.
14. Progress reports phase and processed/total file counts (when known), never filenames or source paths; existing viewer and settings display progress during scheduled/manual refreshes. Concurrent refreshes remain serialized.

## Acceptance Criteria

- [x] Automated tests verify the JS source no longer contains the O(n²) per-card index lookup.
- [x] Automated tests verify a hard grid page-size constant <= 240 and pagination controls in the viewer.
- [x] Automated tests verify concurrent threaded server use and cache headers for generated image assets.
- [x] The synthetic benchmark fixture deterministically creates 6,000 slides and reports JSON size.
- [x] Full repository tests pass (74 passing as of 2026-11-12).
- [x] Browser measurement hooks, downloadable report, and backend scan/build summaries have regression tests.
- [x] Locally verify report download and live interactions in headless Chromium on Pi with 6,000 slides.
- [ ] Perform and pass representative Windows Chrome/Edge benchmark against agreed latency, memory and scroll budgets.
- [ ] Representative Windows browser benchmark remains explicitly pending until run; no unsupported performance claim is made.

## Compatibility and Ownership

`export.json` and SQLite schemas remain compatible. Pagination is purely a presentation concern; filters, search, stars, group/sort semantics, and modal navigation continue to operate on the full client-side result set.

## Open Questions

- Real-hardware target latency/memory budgets will be finalized from the first representative Windows benchmark rather than guessed in code.

## M007c — Reliable Incremental Publication (2026-11-12)

- A completed incremental scan with no new/changed/deleted documents does not rebuild the viewer if an existing complete output matches the installed frontend assets and viewer configuration.
- Newly discovered or modified files that all fail processing do not trigger a rebuild if the indexed SQLite state and complete published viewer remain unchanged; candidates are not committed mutations. A missing/stale viewer, successful update, applied deletion, or requested pause still publishes.
- If a site is missing, incomplete, generated by an older build format, or the web assets/viewer configuration changed, the next refresh rebuilds even when the document scan is unchanged.
- Export JSON, viewer HTML, and static CSS/JS are fully generated in an isolated temporary directory before publication. Each live file is swapped atomically; no reader can observe a partially written individual file or a missing CSS/JS directory during a rebuild.
- A safe completion marker tracks the published frontend/HTML/export identity and is published last. Interrupted publication invalidates the marker so the next refresh retries.
- Publish JSON and static assets before the first-run HTML entrypoint. The local viewer bypasses the cache for export JSON so same-second replacement cannot produce a stale 304 response.
- Scoped scans with additions, updates, or deletions still publish data changes, while no-change scans avoid unnecessary SQLite export/JSON serialization and static copying.
- Do not claim transactional snapshots across several HTTP requests, or immutability of PPTX/PDF thumbnail images while the pipeline is processing them. Those guarantees are distinct follow-on architecture changes.
- Keep original CLI build and rebuild behavior explicit. No database schema migration, cloud service, or platform-specific dependency.

## M007d — Revision-Matched Regression Reports (2026-11-12)

- Parse local synthetic benchmark JSON reports and generate an offline HTML dashboard plus machine-readable comparison report.
- Compare only clean runs with identical library size/text length, workload iteration count, operating system/architecture, and exact browser version; identify mismatches explicitly instead of calling them regressions.
- Compare the most recent compatible *different* Git revisions; allow warning thresholds to be configured without enabling hard failure by default. Missing API metrics and low-sample p95s remain inconclusive.
- Provide charted history, per-metric percentage changes, revision provenance and warnings. No cloud upload, no source document data, and no production dependency.

## M007e — Scan and Restart Recovery (2026-11-12)

- A missing or inaccessible scan root, traversal failure or file stat error must fail the scan before deletion inference or any SQLite mutation; disconnected drives must not appear as mass deletions.
- A corrupt, zero-page or unreadable PDF must not be accepted as a successful empty deck. The scan should report the per-file failure and retain the previously indexed deck and slides for retry.
- Changed presentation metadata and slides should be committed as one SQLite transaction, never deleting old slide rows before a successful render/import. Invalid database operations roll back the old deck content.
- The viewer publication marker must detect a changed SQLite archive after a crash between database commit and viewer publication, even when the subsequent filesystem scan sees no changes. No SQLite schema migration.
- Simulated out-of-space/staging failures must preserve the last complete viewer and remain repairable. Startup/refresh errors remain visible; good data is preserved.
- Tests use temporary PDF/archive fixtures and injected failures; actual Windows COM, filesystem lock semantics, and recovery from power loss remain pending on Windows.


## M007f — Measured Large-Library Optimization (2026-11-12)

- Profile the real viewer JavaScript using the existing 6,000/20,000-slide Chromium workload, identify a confirmed bottleneck and make a targeted shared-code optimization rather than replacing the search architecture.
- Preserve search, sorting, grouping, pagination, starred actions, modal opening, HTML escaping and bounded card count. No Windows-specific changes or backend schema migration.
- Run equivalent clean-revision benchmarks before/after on the Pi, report both the improvement and any regressions, and add a 50,000-slide stress test where resources permit.
- Do not claim representative image/PowerPoint performance; shared placeholder images do not test realistic thumbnail decoding or disk I/O.

## M007h — Bounded Presentation Sidebar (2026-11-15)

- The presentation sidebar must render no more than 100 document rows per page at all library sizes, including after search and navigation.
- Its search must continue to match **all indexed filenames**, including those beyond the first page, using the existing local in-memory dataset.
- Provide accessible Previous/Next buttons, current page and total-match range; handle empty searches, first/last-page boundaries and narrowing search without invalid/empty pages.
- A selected document continues filtering the slide grid across sidebar page changes. Clearing filters or selecting a different document must retain existing folder and main-search semantics.
- Limit the optimization to frontend presentation and instrumentation: no archive, SQLite, export format, or remote query API changes. A newly published frontend may trigger the existing safe static build; original images and source documents remain unchanged.
- Measure before/after DOM-node count, Chrome heap, startup and search on a real Mac1 library using the same headless browser workload; record variance and do not claim a Windows acceptance result.

### M007h Native Acceptance

- [x] Source and browser regression checks: Pi and Mac1 174/174 Python tests; Node 8/8, including off-page filename search and persistent selection.
- [x] Native Mac1 install: arm64 bundle, 17/17 packaging preflight, code-signature verification, verified SQLite/config backup and unchanged semantic configuration.
- [x] Headless Chrome 157 repeated on the same 145,289-page archive: sidebar rows 14,677 → 100; live DOM elements 17,901 → 3,330.
- [ ] Significant JS-heap/startup-search improvement remains unproven; M007g memory work and Windows Chrome/Edge acceptance stay open.
