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

## Documentation Convergence

Update design/requirements/roadmap/README/changelog/handoff with implemented optimizations and clearly distinguish portable validation from pending real-browser measurements.
