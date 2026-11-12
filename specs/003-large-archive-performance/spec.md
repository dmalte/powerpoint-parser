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

## Acceptance Criteria

- [x] Automated tests verify the JS source no longer contains the O(n²) per-card index lookup.
- [x] Automated tests verify a hard grid page-size constant <= 240 and pagination controls in the viewer.
- [x] Automated tests verify concurrent threaded server use and cache headers for generated image assets.
- [x] The synthetic benchmark fixture deterministically creates 6,000 slides and reports JSON size.
- [x] Full repository tests pass (61 passing as of 2026-11-12).
- [x] Browser measurement hooks, downloadable report, and backend scan/build summaries have regression tests.
- [x] Locally verify report download and live interactions in headless Chromium on Pi with 6,000 slides.
- [ ] Perform and pass representative Windows Chrome/Edge benchmark against agreed latency, memory and scroll budgets.
- [ ] Representative Windows browser benchmark remains explicitly pending until run; no unsupported performance claim is made.

## Compatibility and Ownership

`export.json` and SQLite schemas remain compatible. Pagination is purely a presentation concern; filters, search, stars, group/sort semantics, and modal navigation continue to operate on the full client-side result set.

## Open Questions

- Real-hardware target latency/memory budgets will be finalized from the first representative Windows benchmark rather than guessed in code.
