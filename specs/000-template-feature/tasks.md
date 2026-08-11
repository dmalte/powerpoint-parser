# Tasks: {{FEATURE_TITLE}}

- Feature: `{{FEATURE_PATH}}`
- Milestone: {{MILESTONE_ID}}
- Requirements: {{REQUIREMENT_IDS}}

> Live progress record: add, split, reorder, complete, or retire tasks as the
> implementation evolves. Keep `dev/HANDOFF.md` synchronized after meaningful
> progress.

## Preparation

- [ ] T001 Confirm accepted requirements and scope in `spec.md`.
- [ ] T002 Confirm the current implementation approach in `plan.md`.
- [ ] T003 Link the feature from `ROADMAP.md` and verify requirement references.
- [ ] T004 Initialize or refresh `dev/HANDOFF.md` for the selected feature.
- [ ] T005 Run the agent-managed feature pre-implementation gate.

## Implementation

- [ ] T010 Implement the first coherent unit of behavior.
- [ ] T011 Add or update focused tests.
- [ ] T012 Reconcile accepted behavior changes into `spec.md`.
- [ ] T013 Reconcile implementation-strategy changes into `plan.md`.
- [ ] T014 Refresh `dev/HANDOFF.md` after meaningful progress.
- [ ] T015 Implement remaining operator-visible behavior.

## Validation

- [ ] T020 Run focused checks.
- [ ] T021 Run the configured full relevant test suite.
- [ ] T022 Verify acceptance criteria and regression behavior.
- [ ] T023 Reconcile `tasks.md` with actual implementation and validation state.

## Convergence

- [ ] T030 Update requirement statuses and roadmap state.
- [ ] T031 Update consolidated design and changelog where required.
- [ ] T032 Refresh or reset the live handoff to the true continuation state.
- [ ] T033 Confirm `spec.md` matches accepted behavior.
- [ ] T034 Confirm `plan.md` matches the implemented approach.
- [ ] T035 Inspect the final diff and add `.completed` when fully done.
