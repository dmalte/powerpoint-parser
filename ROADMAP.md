# Roadmap

This file defines outcome-level milestones and delivery order. A milestone may span multiple chats and, when useful, multiple features.

## Status Vocabulary

- `planned`: accepted but not currently selected
- `active`: currently being implemented
- `paused`: intentionally stopped but not abandoned
- `blocked`: cannot proceed until a dependency is resolved
- `done`: validated and documented
- `deferred`: accepted for later reconsideration
- `rejected`: explicitly not planned

## Milestones

| ID | Milestone | Outcome | Depends on | Status | Feature |
|---|---|---|---|---|---|
| M001 | Local visual archive foundation | PowerPoint/PDF documents can be indexed incrementally and browsed through the generated local viewer with search and retrieval tools | — | done | historical implementation |
| M002 | Cross-platform packaging | Non-Windows hosts can install the project for PDF-only workflows without requiring `pywin32`, while Windows retains PowerPoint COM rendering | M001 | active | direct maintenance work |
| M003 | Agent-managed development workflow | Repository work is governed by durable requirements, roadmap, living feature records, workflow gates, and a current handoff | M001 | active | repository infrastructure |

## Next Development Selection

No numbered feature is selected yet. After the current direct maintenance changes and workflow bootstrap are validated, choose the next accepted product outcome, add its requirement IDs here, create a `specs/NNN-short-name/` feature record, and set `active_feature` in `PROJECT_WORKFLOW.json`.

## Notes

- Add milestones only for meaningful outcomes, not for every chat.
- Link an active substantial milestone to its selected `specs/<feature>/` directory.
- Direct maintenance may remain featureless when behavior is already defined and localized.
- Keep completed milestones as history.
