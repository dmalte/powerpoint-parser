# Project Agent Instructions

## Required Context

Before meaningful work, read:

1. `PROJECT_WORKFLOW.json`
2. `README.md`
3. `spec/DESIGN_SPEC.md`
4. `spec/REQUIREMENTS.md`
5. `ROADMAP.md`
6. the feature selected by `active_feature`, when configured
7. `dev/HANDOFF.md`

Read the workspace-level `WORKFLOW.md` when available. It defines the shared
mode lifecycles; this file defines repository rules.

Also run:

```powershell
git status --short
git log -5 --oneline
python scripts/workflow_gate.py status
```

Preserve unrelated user changes.

## Workflow Dispatch

Follow `workflow_mode` in `PROJECT_WORKFLOW.json`.

| Mode | Behavior |
|---|---|
| `agent-managed` | Use the living feature workflow below. |
| `direct` | Direct changes are allowed; substantial work may use an agent-managed feature. |
| `hybrid-gated` | Direct fixes are allowed; substantial work uses Spec Kit. |
| `strict` | Behavior changes use Spec Kit. |

Classify work as `direct`, `feature`, `short`, or `full` before editing
production code. `WORKFLOW.md` defines non-default mode details and Spec Kit
sequences. The operator's explicit selection takes precedence over defaults.

## Direct Changes

Use `direct` only for narrow work with already-defined behavior: localized bug
fixes, typos, small visual adjustments, focused regression tests, or contained
internal refactors. Direct work does not require a feature directory.

If investigation reveals a new requirement, architecture, persisted-data
migration, public contract, security boundary, or substantial dependency,
reclassify before implementation continues.

## Agent-Managed Feature Workflow

In `agent-managed` mode, the coding agent—not the operator—automatically creates
and maintains the living feature documents. This maintenance is part of
implementation and does not require a separate operator request.

Substantial work uses one selected directory:

```text
specs/<feature>/
├── spec.md
├── plan.md
└── tasks.md
```

Resolve it from `active_feature` in `PROJECT_WORKFLOW.json`. Do not infer that
every unfinished feature is active. One feature represents one coherent
objective and may span several chats. Do not invoke Spec Kit unless the operator
changes the workflow selection.

### Automatic Living-Document Maintenance

Update authoritative files automatically as work changes:

| Change | Authoritative file |
|---|---|
| Accepted goal, behavior, scope, exclusions, acceptance criteria, ownership | `spec.md` |
| Architecture, components, data flow, compatibility, dependencies, validation strategy | `plan.md` |
| Discovered, reordered, split, completed, retired, or deferred work | `tasks.md` |
| Meaningful progress, decisions, issues, next step, validation state | `dev/HANDOFF.md` |
| Stable current behavior or architecture | `spec/DESIGN_SPEC.md` |
| Stable requirement or status | `spec/REQUIREMENTS.md` |
| Milestone scope, link, dependency, or status | `ROADMAP.md` |
| Notable validated outcome | `CHANGELOG.md` |

Do not rely on chat history as the durable record.

Keep `spec.md` aligned with current accepted feature intent. Reconcile material
behavior or scope changes before or together with code. Do not record temporary
exploration, debugging steps, or internal organization that does not alter
required behavior.

Keep `plan.md` aligned with the approach actually being implemented. Update it
when responsibilities, persistence, data flow, compatibility, dependencies,
interfaces, sequencing, or validation strategy materially change. Git owns
chronological history.

Maintain `tasks.md` continuously:

- add necessary work discovered during implementation;
- split or reorder tasks when needed;
- mark `[x]` only after implementation and relevant validation;
- keep incomplete work unchecked;
- retire obsolete work with a concise reason;
- include testing and documentation-convergence tasks.

Refresh `dev/HANDOFF.md` after meaningful code changes, completed tasks or
phases, material decisions, new issues, changed next steps, or validation
results. Maintain:

- Last Updated
- Active Feature
- Current Objective
- Completed
- Decisions
- Files Changed
- Open Issues
- Next Step
- Validation

Reference feature documents instead of duplicating them. When no continuation
state remains, record a concise completed state or `No interrupted work.`

Before ending meaningful work:

1. reconcile accepted behavior with `spec.md`;
2. reconcile the implemented approach with `plan.md`;
3. reconcile actual progress with `tasks.md`;
4. refresh `dev/HANDOFF.md`;
5. promote stable project truth to consolidated documentation;
6. report remaining code/document divergence.

## Other Workflow Modes

For `direct`, `hybrid-gated`, and `strict`, follow `WORKFLOW.md`. When Spec Kit
is required, verify `spec_kit.enabled`, use the configured integration, select
`short` or `full`, and do not bypass gates by relabeling substantial work as
direct.

## Workflow Gate and Commands

Use exact commands from `PROJECT_WORKFLOW.json`. Empty commands are unresolved.

```powershell
# Narrow correction
python scripts/workflow_gate.py pre-implement --change-class direct

# Agent-managed feature
python scripts/workflow_gate.py pre-implement --change-class feature
```

Override the selected feature only when necessary:

```powershell
python scripts/workflow_gate.py pre-implement `
  --change-class feature `
  --feature specs/<feature>
```

For Spec Kit work, use `short` or `full` as defined in `WORKFLOW.md`. A passing
gate confirms structure only; it does not replace tests, acceptance validation,
document reconciliation, or final diff review.

## Documentation Ownership

- Purpose and setup: `README.md`
- Current intended system: `spec/DESIGN_SPEC.md`
- Requirements and status: `spec/REQUIREMENTS.md`
- Milestones and delivery order: `ROADMAP.md`
- Selected objective, approach, and progress: `specs/<feature>/`
- Live continuation state: `dev/HANDOFF.md`
- Release-level history: `CHANGELOG.md`
- Exact history: Git

Do not create parallel current-state, status, decision, or reusable
implementation-plan files.

## Readiness and Escalation

Before an agent-managed feature, verify that the selected feature exists;
`spec.md`, `plan.md`, and `tasks.md` are meaningful; tasks have actionable
checkboxes; requirement and milestone references are valid; `ROADMAP.md` links
the feature; validation is planned; the handoff identifies the feature; and
unrelated working-tree changes are preserved.

Update accepted requirements and feature documents before implementing newly
discovered material behavior. Surface incompatible migrations, new public
contracts, security boundaries, major architectural replacements, or
substantial production dependencies before proceeding.

## Git and Safety

Follow Git permissions in `PROJECT_WORKFLOW.json`. Use Conventional Commits,
include tests and documentation with related changes, and reference requirement
IDs where applicable.

Never commit secrets, overwrite unrelated work, perform destructive operations
without authorization, modify read-only external repositories, change public
contracts without accepted requirements, add unexplained production
dependencies, or mark work complete without validation evidence.

## Done

Work is complete only when relevant checks pass; `spec.md`, `plan.md`, and
`tasks.md` match reality; requirements, roadmap, and consolidated documentation
are current; the handoff reflects the true continuation state; and the final
diff contains no unrelated changes.

Agent-managed completion does not require Spec Kit artifacts or commands.
