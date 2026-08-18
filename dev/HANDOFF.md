# Handoff

- Last Updated: 2026-08-18T12:35:29-07:00
- Active Feature: `specs/001-windows-desktop-agent`

## Current Objective

Refine and implement **Windows Packaged Desktop Agent** for milestone M004.

## Completed

- Accepted and recorded the three-phase deployment sequence in requirements, roadmap, and consolidated design documentation.
- Created and selected `specs/001-windows-desktop-agent` for Phase 1 / M004 / REQ-DEPLOY-001.
- Refined the living feature spec, implementation plan, and task list for the per-user Windows desktop-agent approach.
- Implemented the Phase 1 runtime foundation: per-user app-data paths, installed config discovery, `init-config`, long-running `agent`, scheduled incremental refresh, durable per-user agent logging, and PyInstaller-frozen web-resource lookup.
- Added focused portable tests for the installed runtime and agent lifecycle.
- Added the Phase 1 Windows packaging scaffold: console and windowless PyInstaller entry points/spec, per-user Inno Setup installer, user-logon startup registration, and a PowerShell build helper.
- Added a documented Windows build/install/PPTX smoke-test procedure and portable structural tests for the packaging definitions.
- Updated README, consolidated design, and changelog to describe implemented runtime/packaging behavior while keeping M004 / REQ-DEPLOY-001 active pending Windows smoke validation.

## Decisions

- Workflow: agent-managed.
- Phase 1 is REQ-DEPLOY-001 / M004; Phase 2 and Phase 3 are accepted but remain out of active implementation scope.
- Use a per-user interactive desktop agent rather than a Windows Service so PowerPoint COM remains in the signed-in user session.
- Preserve the existing local-first SQLite/static-viewer architecture and explicit developer `--config` workflows.
- PyInstaller is the self-contained Windows build mechanism; Inno Setup is the per-user installer layer. Their definitions are implemented but still require a Windows build/install smoke test.

## Files Changed

- `src/ppt_visual_archive/platform_paths.py`
- `src/ppt_visual_archive/config.py`
- `src/ppt_visual_archive/cli.py`
- `src/ppt_visual_archive/agent.py`
- `src/ppt_visual_archive/builder.py`
- `src/ppt_visual_archive/utils.py`
- `tests/test_agent_runtime.py`
- `packaging/windows/PowerPointVisualArchive.spec`
- `packaging/windows/PowerPointVisualArchive.iss`
- `packaging/windows/build.ps1`
- `packaging/windows/pptviewer_launcher.py`
- `packaging/windows/agent_launcher.py`
- `packaging/windows/README.md`
- `tests/test_windows_packaging.py`
- `pyproject.toml`
- `README.md`
- `CHANGELOG.md`
- `spec/DESIGN_SPEC.md`
- `specs/001-windows-desktop-agent/tasks.md`
- `dev/HANDOFF.md`

## Open Issues

- The PyInstaller executables and Inno Setup installer have not been built on Windows in this session; executable/install/logon/PPTX COM behavior therefore remains unverified.
- Product icon, final branding, and code-signing identity are deferred beyond Phase 1 validation / into later distribution hardening.

## Next Step

Run the Windows build/install/PPTX smoke test in `packaging/windows/README.md`. If it passes, record the Windows/Office versions and results, then converge REQ-DEPLOY-001 / M004 and the feature completion state.

## Validation

- `python scripts/workflow_gate.py pre-implement --change-class feature` passes for `specs/001-windows-desktop-agent`.
- `.venv/bin/python -m pytest tests/test_agent_runtime.py -q` → 7 passed.
- `.venv/bin/python -m pytest tests/test_agent_runtime.py tests/test_windows_packaging.py -q` → 9 passed.
- `.venv/bin/python -m pytest tests -q` → 45 passed.
- `.venv/bin/python -m py_compile ... PowerPointVisualArchive.spec` and the new Python launch/runtime modules → passed.
- Development dependencies were installed into the existing project `.venv` using the repository setup command so focused/full tests could run.
- Windows PyInstaller/Inno Setup/PPTX smoke validation: not run on this non-Windows host; T032 remains open.
- The local gate does not support the workspace-documented `--owner` writer-lease argument; repository-local gate semantics are being followed for this feature.
