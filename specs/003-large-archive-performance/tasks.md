# Tasks: Large Archive Viewer Performance

- Feature: `specs/003-large-archive-performance`
- Milestone: M007
- Requirements: REQ-PERF-001

## Preparation

- [x] T001 Confirm 6,000-slide target, frontend-first scope, and compatibility in `spec.md`.
- [x] T002 Record pagination/search-cache/server-cache approach in `plan.md`.
- [x] T003 Link/activate M007 and REQ-PERF-001.
- [x] T004 Refresh handoff and run the feature pre-implementation gate.

## Browser Performance

- [x] T010 Normalize deck/slide derived fields once after data load.
- [x] T011 Cache scoped lowercased search blobs instead of rebuilding them for every query.
- [x] T012 Replace full-result DOM rendering with fixed-size page rendering (<=240 cards).
- [x] T013 Add pagination controls/range display and reset/clamp behavior.
- [x] T014 Remove per-card `slides.indexOf(slide)` and batch DOM insertion.

## Server and Benchmark

- [x] T020 Add safe cache headers for generated deck image assets while preserving no-store API responses.
- [x] T021 Add deterministic 6,000-slide benchmark/export fixture generator.
- [x] T022 Add focused regression tests for browser source invariants, fixture, and HTTP cache behavior.

## Validation and Convergence

- [x] T030 Run focused M007 tests and the 6,000-slide fixture.
- [x] T031 Run full repository tests.
- [x] T032 Update stable documentation/changelog/handoff.
- [x] T033 Record representative Windows browser benchmark as pending if unavailable.
- [x] T034 Inspect final diff; do not mark M007 done until real-browser acceptance evidence exists.
