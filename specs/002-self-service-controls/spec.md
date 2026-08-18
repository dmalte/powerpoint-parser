# Self-Service Desktop Controls

- Feature: `specs/002-self-service-controls`
- Workflow: agent-managed
- Status: active
- Milestone: M005
- Requirements: REQ-DEPLOY-002

> Living document: update this file whenever accepted behavior, scope, or validation changes.

## Objective

Make the installed archive usable and supportable without a console by adding a Windows notification-area control surface and a localhost browser settings/status surface backed by the running per-user agent.

## Scope

### In Scope

- Agent status including idle/scanning/error state, last refresh, and last error.
- Manual `Scan Now` while preserving single-refresh serialization.
- Browser settings for scan roots, file types, and refresh interval, persisted to the existing YAML config.
- Browser actions to open the archive and logs.
- Windows tray menu for Open Archive, Scan Now, Settings, View Logs, Restart, and Exit.
- Localhost-only control APIs used by the browser and tray.
- Preserve current CLI/development workflows and local-first storage.

### Out of Scope

- Code signing, managed policy, centralized administration, auto-update, or endpoint-management integration.
- Cloud accounts, synchronization, or remote access.
- Completing the still-pending M004 Windows installer smoke test.

## Required Behavior

1. The agent exposes localhost-only JSON endpoints for status, settings, and manual refresh.
2. Settings changes validate scan roots, file types, and refresh interval before replacing the authoritative YAML config.
3. A successful settings update takes effect for subsequent refreshes without requiring YAML editing.
4. Manual and scheduled scans never overlap. A manual request received while a refresh is already running reports that state rather than starting a second scan.
5. The browser settings page can view/update settings, trigger a scan, open the archive, and open the log folder/file where supported.
6. On Windows, the installed agent starts a notification-area icon using existing `pywin32`; no additional tray dependency is introduced.
7. Tray actions open the archive/settings/logs, trigger a scan, restart the current agent process, or exit it cleanly.
8. Non-Windows/PDF-only development use continues without importing Windows-only tray modules.

## Acceptance Criteria

- [ ] Portable tests cover status transitions, serialized refresh, settings validation/persistence, and API behavior.
- [ ] The generated viewer includes a Settings entry point and settings page.
- [ ] Windows tray implementation is packaged and import-isolated from non-Windows hosts.
- [ ] Full repository tests pass.
- [ ] A later Windows smoke test verifies the notification icon and all menu actions in the packaged app.

## Compatibility and Ownership

`config.yaml` remains the authoritative settings store. Existing config keys continue to load; Phase 2 adds a persisted processing refresh interval with a backward-compatible default. The local agent remains bound to `127.0.0.1`; control APIs are not intended for remote access.

## Open Questions

- Final icon artwork/branding remains deferred; the tray implementation may use a generated placeholder icon until branding is supplied.
