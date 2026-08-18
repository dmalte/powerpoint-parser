# Tasks: Self-Service Desktop Controls

- Feature: `specs/002-self-service-controls`
- Milestone: M005
- Requirements: REQ-DEPLOY-002

## Preparation

- [x] T001 Confirm accepted requirements and scope in `spec.md`.
- [x] T002 Confirm the implementation approach in `plan.md`.
- [x] T003 Link the feature from `ROADMAP.md` and activate REQ-DEPLOY-002.
- [x] T004 Refresh `dev/HANDOFF.md` for the selected feature.
- [x] T005 Run the feature pre-implementation gate.

## Runtime and API

- [x] T010 Add backward-compatible persisted refresh interval and settings validation/update helpers.
- [x] T011 Refactor agent lifecycle around a thread-safe runtime with status and serialized manual/scheduled refresh.
- [x] T012 Add localhost status/settings/scan/shutdown control APIs and threaded static serving.
- [x] T013 Add focused runtime/config/server tests.

## User Experience

- [x] T020 Generate a browser settings/status page and Settings entry point from the viewer.
- [x] T021 Add Windows notification-area controls using existing pywin32 without breaking non-Windows imports.
- [x] T022 Wire tray restart/exit/open/log/scan/settings behavior into the running agent.
- [x] T023 Update Windows packaging analysis if needed for tray modules.

## Validation and Convergence

- [x] T030 Run focused Phase 2 tests.
- [x] T031 Run the full repository test suite.
- [x] T032 Update README, changelog, design, requirement/roadmap state, and handoff.
- [x] T033 Record Windows tray/menu smoke validation as pending if not run.
- [ ] T034 Inspect final diff; only mark feature complete after applicable acceptance validation.
