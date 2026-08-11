# Feature Records

Each numbered directory records one coherent implementation objective. A feature
may span multiple chats. A chat does not automatically create a feature.

Agent-managed and Spec Kit workflows share the same durable core artifacts:

```text
spec.md
plan.md
tasks.md
```

For agent-managed features these are living documents:

- `spec.md` tracks current accepted behavior and scope;
- `plan.md` tracks the actual implementation strategy;
- `tasks.md` tracks current work and progress;
- `dev/HANDOFF.md` is refreshed as a live continuation snapshot.

Agent-managed features do not require generated checklists, research documents,
contracts, or analysis reports.

## Naming

Use:

```text
NNN-short-kebab-name
```

Examples:

```text
001-initial-foundation
002-project-idea-workspace
```

`000-template-feature` is a scaffold and must never be treated as active work.

## Completion

Completed feature directories remain historical. Add a `.completed` marker only
after implementation, validation, living feature documents, requirement status,
roadmap, consolidated design, changelog, and handoff have converged.
