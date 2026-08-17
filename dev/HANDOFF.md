# Handoff

- Last Updated: 2026-08-17
- Active Feature: Not selected

## Current Objective

Finish validating the current direct cross-platform packaging edits, then select the next substantial product objective through the new agent-managed spec workflow.

## Completed

- Hardened the public exporter to refuse any staging target containing `.git` metadata and refreshed `_export/powerpoint-parser`; the project privacy scan and workspace-wide privacy scan both pass with 0 blocking findings.
- The project already provides an incremental local PowerPoint/PDF visual archive, generated viewer, advanced search, date filtering, and local slide starring.
- Added the standard repository agent/spec infrastructure based on `/home/nandemo/dev/project-template`.
- Added stable requirements, roadmap milestones, reusable feature templates, workflow-gate helpers, and this live handoff.

## Decisions

- Workflow mode is `agent-managed`; Spec Kit is disabled unless explicitly selected later.
- Small, already-defined maintenance changes may use the `direct` path.
- Substantial behavior changes use one numbered `specs/<feature>/` directory containing living `spec.md`, `plan.md`, and `tasks.md`.
- Windows remains the PowerPoint rendering platform; non-Windows installations are supported for PDF-only workflows and viewer use.

## Files Changed

Workflow bootstrap adds `AGENTS.md`, `PROJECT_WORKFLOW.json`, `ROADMAP.md`, `spec/REQUIREMENTS.md`, `specs/`, `scripts/workflow_gate.py`, `scripts/new_feature.py`, and `dev/HANDOFF.md`.

Pre-existing uncommitted user work remains in `README.md`, `pyproject.toml`, and generated `src/ppt_visual_archive.egg-info/*` metadata; those edits make `pywin32` Windows-conditional and document Linux/PDF-only installation.

## Open Issues

- The current packaging edits have not yet been committed or fully validated as part of this workflow-bootstrap task.
- No next numbered product feature has been selected.
- Consolidated design documentation needs to stay synchronized with PDF support and cross-platform constraints as those behaviors evolve.

## Next Step

Run the workflow helper tests and the project test suite, validate the existing cross-platform packaging edits, then either complete that direct maintenance change or create/select the next numbered feature with `python scripts/new_feature.py`.

## Validation

- `python tools/export_public_bundle.py ../_export/powerpoint-parser --force` → 0 private-data findings.
- Exporter compiles successfully and explicitly refuses a staging target containing `.git` metadata.
- Cross-project staging scan reports no secrets, private IPs, non-synthetic email addresses, user-home paths, symlinks, or `.git` metadata in `_export/powerpoint-parser`.
- `python scripts/workflow_gate.py status` passes and reports `agent-managed` mode with no active feature selected.
- `python -m py_compile scripts/workflow_gate.py scripts/new_feature.py` passes.
- Workflow and project pytest suites are currently blocked because neither the system Python nor the repository `.venv` has `pytest` installed (`No module named pytest`).
- Primary full check after installing development dependencies: `python -m pytest tests -q`.

## Change Log

### 2026-08-17

- Hardened and revalidated the public staging boundary; no Git metadata is permitted in generated staging.
