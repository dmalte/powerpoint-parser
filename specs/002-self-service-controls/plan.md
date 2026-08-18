# Implementation Plan: Self-Service Desktop Controls

- Feature: `specs/002-self-service-controls`
- Milestone: M005
- Requirements: REQ-DEPLOY-002

## Current Context

The Phase 1 agent already owns refresh scheduling and localhost serving, but it has no durable runtime status model, control API, browser settings page, or tray surface. Configuration is YAML and the refresh interval is currently a CLI-only value.

## Approach

1. Add a small thread-safe agent runtime/control object that owns status, refresh locking, mutable interval, config reload/persistence, and shutdown/restart requests.
2. Extend the localhost server with JSON control endpoints and use `ThreadingHTTPServer` so API/static requests and control actions can coexist.
3. Add a generated settings page and JS client that talks only to localhost endpoints.
4. Add a Windows-only tray module using `pywin32`, already required on Windows, and wire it to the same runtime actions.
5. Package the tray module with the existing frozen agent.

## Components and Responsibilities

- `agent.py`: runtime state, serialized refresh, scheduled/manual refresh, lifecycle, restart/exit coordination.
- `server.py`: localhost control API and static serving; no archive business logic.
- `config.py`: persisted refresh interval and validated settings updates.
- `tray.py`: Windows notification-area menu and callbacks; Windows imports remain lazy/isolated.
- `builder.py` + `web/`: settings page generation and viewer Settings link.
- packaging spec: include Windows tray imports if PyInstaller analysis needs them.

## Data Flow and Persistence

Browser/tray actions call the in-process runtime directly or through `127.0.0.1`. Settings writes replace the existing YAML configuration using the existing serializer. The runtime then reloads settings for future refreshes. Archive/index data ownership is unchanged.

## Compatibility and Risk

- Existing configs without `processing.scan_interval_seconds` use 1800 seconds.
- Windows tray imports must never break non-Windows import/test paths.
- Manual scan and scheduled scan share one non-blocking refresh lock.
- Control APIs remain bound to loopback; they are not authenticated for remote exposure and must not be rebound to external interfaces.
- Restart is process-level and cannot be fully validated on this non-Windows host.

## Implementation Phases

1. Runtime/config/API foundation with portable tests.
2. Browser settings UI and Windows tray integration.
3. Full tests, documentation convergence, and explicit Windows-smoke deferral.

## Validation

- Unit tests for config compatibility and validation.
- Runtime tests for status transitions, refresh serialization, and interval updates.
- HTTP tests for status/settings/scan endpoints.
- Structural tests for tray import isolation and packaging.
- Full `pytest tests -q`.
- Windows packaged smoke test later for icon/menu/restart/exit behavior.

## Documentation Convergence

Update `spec/DESIGN_SPEC.md`, `spec/REQUIREMENTS.md`, `ROADMAP.md`, `README.md`, `CHANGELOG.md`, and `dev/HANDOFF.md` with implemented and still-unverified behavior.
