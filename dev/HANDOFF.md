# Handoff

- Last Updated: 2026-08-18T14:12:15-07:00
- Active Feature: `specs/002-self-service-controls`

## Current Objective

Implement M005 self-service desktop controls, then proceed directly to M007 large-archive performance as requested while M004 installer smoke validation remains deferred.

## Completed

- Created/selected `specs/002-self-service-controls`; M005 is active and M004 is paused only for Windows validation.
- Added backward-compatible persisted `processing.scan_interval_seconds`.
- Refactored the agent around `AgentRuntime` with thread-safe status, serialized manual/scheduled refresh, settings persistence, and restart/exit coordination.
- Added loopback-only threaded server controls for status, settings, Scan Now, logs, and shutdown/restart.
- Added generated browser settings/status page and viewer Settings entry point.
- Added Windows notification-area controls using existing `pywin32` only.
- Updated PyInstaller hidden imports for tray support.
- Added focused portable tests for settings persistence, validation, scan serialization, HTTP controls, and tray import isolation.

## Decisions

- Reuse `pywin32` for tray behavior; no new production dependency.
- Keep `config.yaml` authoritative and local; browser settings update the same file.
- Keep control APIs loopback-only and unauthenticated for local use; do not expose the server externally.
- Manual and scheduled refreshes share one non-overlapping lock.
- M005 implementation can proceed before M004 Windows smoke validation by explicit operator direction.

## Files Changed

- `PROJECT_WORKFLOW.json`
- `ROADMAP.md`
- `spec/REQUIREMENTS.md`
- `spec/DESIGN_SPEC.md`
- `README.md`
- `CHANGELOG.md`
- `specs/002-self-service-controls/*`
- `src/ppt_visual_archive/config.py`
- `src/ppt_visual_archive/cli.py`
- `src/ppt_visual_archive/agent.py`
- `src/ppt_visual_archive/server.py`
- `src/ppt_visual_archive/tray.py`
- `src/ppt_visual_archive/builder.py`
- `web/templates/index.html.j2`
- `web/templates/settings.html.j2`
- `web/static/js/settings.js`
- `packaging/windows/PowerPointVisualArchive.spec`
- `tests/test_agent_runtime.py`
- `tests/test_self_service_controls.py`

## Open Issues

- M004 installer/PPTX/logon behavior remains untested on Windows.
- M005 notification-area icon/menu/restart behavior remains untested in a packaged Windows build; portable behavior is validated.

## Next Step

Checkpoint M005 implementation, then create/select the M007 large-archive performance feature and implement browser/server optimizations with a reproducible 6,000-slide benchmark fixture.

## Validation

- `python scripts/workflow_gate.py pre-implement --change-class feature` → passed for `specs/002-self-service-controls`.
- `.venv/bin/python -m pytest tests/test_agent_runtime.py tests/test_self_service_controls.py -q` → 13 passed.
- `.venv/bin/python -m pytest tests -q` → 51 passed.
- Packaged Windows tray smoke validation: not run on this non-Windows host.
