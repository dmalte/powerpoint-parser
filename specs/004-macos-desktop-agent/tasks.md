# Tasks — macOS Desktop Agent Preparation

- Feature: specs/004-macos-desktop-agent
- Milestone: M008
- Requirements: REQ-MAC-001

## Preparation
- [x] T001 Establish Mac scope and pass feature workflow gate.

## Rendering
- [x] T010 Implement Mac PowerPoint AppleScript temporary PDF converter and shared rasterized slide images with timeout/cleanup.
- [x] T011 Add explicit LibreOffice backend and platform factory; keep Windows COM unchanged.
- [x] T012 Tests for metadata/search parity, renderer failures, conversion and cleanup.

## Local UX and Packaging
- [x] T020 Add macOS per-user paths, Finder open/reveal and tests.
- [x] T021 Add Mac LaunchAgent and build/install scaffolding plus static preflight.

## Validation
- [x] T030 Run full Pi tests and mock-converter integration.
- [x] T031 Update README/design/requirements/roadmap/changelog/handoff; inspect diff and commit locally.
- [ ] T032 Real macOS PowerPoint, packaging, permissions, fidelity, login validation pending.

## M008a — Versioned image publication
- [x] T040 Introduce immutable per-deck image generations and preserve the previous viewer's assets on failed or interrupted processing.
- [x] T041 Add PDF/PPTX success/rollback, active-reader, and no-leak regression tests.

## M008b — Installer lifecycle
- [x] T050 Stage app/CLI upgrades, roll back on failure, and support explicit data-preserving uninstall.
- [x] T051 Test new install, upgrade, failure injection, rollback and repeatable uninstall on Pi.

## M008c — Readiness diagnostics
- [x] T060 Add native dependency/config/filesystem permission/readiness checks with a path-free JSON report.
- [x] T061 Test misconfiguration, unavailable binaries, no data leakage and healthy state.

## M008d — Reference fidelity suite
- [x] T070 Build deterministic PPTX reference decks with complex content and expected metadata.
- [x] T071 Implement per-slide comparison metrics plus offline HTML/JSON report and tests.

## Convergence
- [x] T080 Run full tests, update architecture/requirements/roadmap/handoff, review diff and checkpoint locally.
- [ ] T081 Actual Mac native PowerPoint, install, permissions, fidelity and performance acceptance still pending.

## Mac1 native qualification (2026-11-12)

- [x] T090 Fast-forward clean Mac1 checkout from Pi development repo and install isolated development dependencies; run 132 portable tests.
- [x] T091 Build native arm64 app/CLI, verify 17 binary/source checks and ad hoc code signature; scan/build one real PDF with packaged CLI and verify app localhost startup/shutdown.
- [x] T092 Add reproducible, path-free native PowerPoint smoke report; reproduce export error -9074 and document direct JPG dictionary availability.
- [ ] T093 Resolve native PowerPoint export environment/permissions and verify actual PPTX slides and image comparison against reference decks.
- [ ] T094 With approval, install per-user LaunchAgent and validate login, upgrade, rollback, uninstall, and user-facing access.

## M008e — Hidden slide parity
- [x] T100 Preserve hidden slides by temporarily unhiding only the private PPTX rendering copy; keep original untouched.
- [x] T101 Add regression tests for hidden slides, sequence mapping, notes and original document immutability.
- [x] T102 Update docs/handoff, run full portable tests and checkpoint locally.
- [x] T103 Native Mac interactive six-slide PowerPoint smoke test and image/notes acceptance (2026-11-12: 6/6, all images valid, titles/notes and original checksum verified).
