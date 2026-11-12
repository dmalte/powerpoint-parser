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

## Performance Feedback Hooks (2026-11-12)

- [x] T040 Add bounded browser performance sampler and downloadable JSON report panel.
- [x] T041 Record real viewer fetch/parse/normalization/search/sort/grid/modal/image/scroll timing.
- [x] T042 Record path-free backend scan/build stage timing and recent local JSONL runs.
- [x] T043 Provide local backend report endpoint and include events when exporting the browser report.
- [x] T044 Add portable regression tests and live browser smoke validation (6,000 slides, headless Chromium on Pi).
- [x] T045 Reconcile README, design, requirements, roadmap, changelog, and handoff, then inspect final diff.

## M007a/M007b — Automated Baselines and Responsive Startup (2026-11-12)

- [x] T050 Implement a dependency-light, repeatable 6,000/20,000-slide headless-browser benchmark that saves per-scenario metrics including revision/browser, with explicit synthetic fixture limitations.
- [x] T051 Implement asynchronous initial refresh while the agent's HTTP server starts immediately; preserve serialized manual/scheduled refreshes and failure reporting.
- [x] T052 Expose numeric, path-free scan/build progress and a first-run loading/status page; show progress in existing viewer and settings.
- [x] T053 Add automated tests for startup ordering, pending/error/ready behavior, progress API, benchmark orchestration, and bounded DOM.
- [x] T054 Run complete tests and representative Pi benchmark, reconcile durable documentation and final diff, and checkpoint changes locally without pushing.


## M007c — Reliable Incremental Updates (2026-11-12)

- [x] T060 Record accepted no-op freshness, atomic-file publication, and failure-retry semantics in feature docs.
- [x] T061 Add lightweight published-viewer fingerprint/completion marker and no-change rebuild bypass.
- [x] T062 Stage complete JSON/HTML/CSS/JS output, publish each file atomically without removing live directories, and invalidate marker on interrupted commit.
- [x] T063 Validate first run, unchanged/changed/deleted refresh, missing/stale output, failure recovery and concurrent browser readers.
- [x] T064 Run full tests, collect performance evidence, reconcile docs/handoff, inspect diff, and commit locally without pushing.

## M007d — Performance Regression Tracking (2026-11-12)

- [x] T070 Implement compatible-run matching and configurable regression warning evaluator.
- [x] T071 Generate offline HTML trends and machine-readable JSON comparing committed revisions.
- [x] T072 Test clean/dirty matching, thresholds, incomplete p95s, HTML escaping and CLI integration.
- [x] T073 Validate against Pi benchmark history, reconcile documentation, and checkpoint locally without pushing.

## M007e — Recovery and Fault Tolerance (2026-11-12)

- [x] T080 Guard missing/inaccessible root traversal to prevent false deletions.
- [x] T081 Make changed PDF/PowerPoint deck replacement transactional; preserve prior rows on failures and reject invalid PDFs.
- [x] T082 Detect DB changes missed by the published viewer after interrupted refresh; recover on restart.
- [x] T083 Add deterministic permission, corrupt-document, SQL failure, low-disk and restart-recovery tests.
- [x] T084 Run tests, review actual limitations, update docs/handoff and commit locally.

## M007f — Evidence-Led Large Library Optimization (2026-11-12)

- [x] T090 Capture committed 6,000/20,000-slide baseline and identify measured bottlenecks.
- [x] T091 Optimize a confirmed shared frontend/backend bottleneck without changing user-visible semantics.
- [x] T092 Add regression checks for correctness, accessibility and bounded rendering.
- [x] T093 Run comparable post-change benchmarks and a 50,000-slide synthetic stress case.
- [x] T094 Update performance docs and handoff, run full suite, inspect diff and commit locally.

## Validation and Convergence

- [x] T030 Run focused M007 tests and the 6,000-slide fixture.
- [x] T031 Run full repository tests.
- [x] T032 Update stable documentation/changelog/handoff.
- [x] T033 Record representative Windows browser benchmark as pending if unavailable.
- [x] T034 Inspect final diff; do not mark M007 done until real-browser acceptance evidence exists.
