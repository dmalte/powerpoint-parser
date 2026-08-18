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
| M004 | Phase 1 — Windows packaged desktop agent | Colleagues can install a per-user Windows build that runs in the signed-in user session, owns the local archive server, refreshes incrementally, and starts at logon without Git/Python/console setup | M001, M002 | active | specs/001-windows-desktop-agent |
| M005 | Phase 2 — Self-service desktop experience | Installed users can control status, scanning, settings, logs, restart, and archive opening through tray/browser UI without editing YAML or using a console | M004 | planned | not selected |
| M006 | Phase 3 — Enterprise distribution | IT can distribute signed builds silently with managed defaults, diagnostics/version visibility, and a company-suitable update path | M005 | planned | not selected |
| M007 | Large-archive viewer performance | The local viewer remains responsive with at least 6,000 indexed slides/pages using measured browser/server performance budgets and bounded DOM rendering | M005 | planned | not selected |

## Deployment Sequence

The accepted rollout is intentionally staged:

1. **Phase 1:** package the existing local-first application as a per-user Windows desktop agent and installer. Keep PowerPoint COM automation in the interactive user session rather than a Windows Service.
2. **Phase 2:** add tray controls and browser-based settings so normal operation and troubleshooting are self-service.
3. **Phase 3:** add signing, unattended deployment, managed defaults, diagnostics, and update/distribution support for company-wide rollout.

## Next Development Selection

`specs/001-windows-desktop-agent` is the selected substantial feature and implements M004 / REQ-DEPLOY-001. Phases 2 and 3 remain accepted roadmap outcomes but are not active implementation scope. M007 / REQ-PERF-001 is also accepted as a later performance milestone; it should begin with benchmarking the existing viewer at 6,000 slides before selecting optimizations.

## Notes

- Add milestones only for meaningful outcomes, not for every chat.
- Link an active substantial milestone to its selected `specs/<feature>/` directory.
- Direct maintenance may remain featureless when behavior is already defined and localized.
- Keep completed milestones as history.
