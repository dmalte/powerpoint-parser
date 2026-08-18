# Handoff

- Last Updated: 2026-08-18T12:24:54-07:00
- Active Feature: `specs/001-windows-desktop-agent`

## Current Objective

Refine and implement **Windows Packaged Desktop Agent** for milestone M004.

## Completed

- Accepted and recorded the three-phase deployment sequence in requirements, roadmap, and consolidated design documentation.
- Created and selected `specs/001-windows-desktop-agent` for Phase 1 / M004 / REQ-DEPLOY-001.
- Refined the living feature spec, implementation plan, and task list for the per-user Windows desktop-agent approach.
- Implemented the Phase 1 runtime foundation: per-user app-data paths, installed config discovery, `init-config`, long-running `agent`, scheduled incremental refresh, durable per-user agent logging, and PyInstaller-frozen web-resource lookup.
- Added focused portable tests for the installed runtime and agent lifecycle.

## Decisions

- Workflow: agent-managed.
- Phase 1 is REQ-DEPLOY-001 / M004; Phase 2 and Phase 3 are accepted but remain out of active implementation scope.
- Use a per-user interactive desktop agent rather than a Windows Service so PowerPoint COM remains in the signed-in user session.
- Preserve the existing local-first SQLite/static-viewer architecture and explicit developer `--config` workflows.
- PyInstaller is the planned self-contained build mechanism; Inno Setup is the planned per-user installer layer.

## Files Changed

- `src/ppt_visual_archive/platform_paths.py`
- `src/ppt_visual_archive/config.py`
- `src/ppt_visual_archive/cli.py`
- `src/ppt_visual_archive/agent.py`
- `src/ppt_visual_archive/builder.py`
- `src/ppt_visual_archive/utils.py`
- `tests/test_agent_runtime.py`
- `specs/001-windows-desktop-agent/tasks.md`
- `dev/HANDOFF.md`

## Open Issues

- Windows executable/installer smoke validation requires a Windows build host and has not yet been performed.
- Product icon, final branding, and code-signing identity are deferred beyond the runtime-foundation slice.

## Next Step

Add the Windows packaging layer: PyInstaller build definition, per-user Inno Setup installer, and documented Windows smoke-test procedure.

## Validation

- `python scripts/workflow_gate.py pre-implement --change-class feature` passes for `specs/001-windows-desktop-agent`.
- `.venv/bin/python -m pytest tests/test_agent_runtime.py -q` → 7 passed.
- Development dependencies were installed into the existing project `.venv` using the repository setup command so focused tests could run.
- The local gate does not support the workspace-documented `--owner` writer-lease argument; repository-local gate semantics are being followed for this feature.
