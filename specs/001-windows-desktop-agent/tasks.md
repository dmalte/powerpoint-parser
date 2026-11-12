# Tasks: Windows Packaged Desktop Agent

- Feature: `specs/001-windows-desktop-agent`
- Milestone: M004
- Requirements: REQ-DEPLOY-001

> Live progress record: add, split, reorder, complete, or retire tasks as the
> implementation evolves. Keep `dev/HANDOFF.md` synchronized after meaningful
> progress.

## Preparation

- [x] T001 Record the accepted three-phase deployment requirements and Phase 1 scope in `spec.md`.
- [x] T002 Record the Phase 1 architecture, persistence, packaging, and validation strategy in `plan.md`.
- [x] T003 Link M004/M005/M006 and REQ-DEPLOY-001/002/003 in consolidated roadmap/requirements/design documentation.
- [x] T004 Select `specs/001-windows-desktop-agent` and refresh `dev/HANDOFF.md`.
- [x] T005 Run and pass the agent-managed feature pre-implementation gate.

## Phase 1 Runtime Foundation

- [x] T010 Add per-user application paths and installed config discovery while preserving explicit/development config precedence.
- [x] T011 Add `init-config` to create per-user configuration and archive directories without manual YAML editing.
- [x] T012 Add the long-running `agent` controller/CLI for initial refresh, localhost serving, and optional periodic incremental refresh.
- [x] T013 Make viewer web-resource discovery work in both source and PyInstaller-frozen layouts.
- [x] T014 Add focused automated tests for T010-T013 and refresh the handoff.

## Phase 1 Windows Packaging

- [x] T020 Add a Windows PyInstaller build definition that includes runtime dependencies and viewer web assets.
- [x] T021 Add a per-user Inno Setup installer with Start Menu launch and automatic user-logon agent startup.
- [x] T022 Document the Windows build/install/smoke-test procedure.

## M004a — Installer Build Preflight (2026-11-12)

- [x] T040 Implement portable static validation of installer specs, build script, launcher modules and bundled frontend assets.
- [x] T041 Fail Windows build on native subprocess errors and missing setup artifact, with version checks.
- [x] T042 Add optional Windows artifact presence/signature validation and path-free JSON report.
- [x] T043 Test known-good/known-bad preflight fixtures and run full portable suite.
- [x] T044 Reconcile packaging documentation, roadmap and handoff; checkpoint locally without claiming Windows smoke acceptance.

## Validation and Convergence

- [x] T030 Run focused tests for the runtime foundation.
- [x] T031 Run the configured full relevant test suite.
- [ ] T032 Perform and record the Windows packaged-build/install/PPTX smoke test.
- [x] T033 Update README and changelog for validated Phase 1 behavior and clearly label pending Windows smoke validation.
- [x] T034 Reconcile requirement, roadmap, design, feature documents, and handoff with actual implementation/validation state.
- [ ] T035 Inspect the final diff and add `.completed` only after M004 acceptance criteria are validated.
