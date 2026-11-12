# Windows Packaged Desktop Agent

- Feature: `specs/001-windows-desktop-agent`
- Workflow: agent-managed
- Status: active
- Milestone: M004
- Requirements: REQ-DEPLOY-001

> Living document: update this file whenever the operator accepts a material
> change to behavior, scope, exclusions, acceptance criteria, compatibility,
> data ownership, or included requirement IDs.

## Objective

Deliver Phase 1 of the accepted Windows rollout: a per-user packaged desktop
agent that can be installed and started without Git, a separately installed
Python runtime, virtual-environment setup, console startup, or routine YAML
editing. The agent must remain local-first and run PowerPoint automation in the
signed-in user's interactive session.

## Motivation

The current developer workflow requires cloning the repository, preparing Python,
editing a configuration file, and manually starting commands. That is unsuitable
for deployment to colleagues. Phase 1 establishes the runtime and packaging
boundary needed for a normal Windows installer while preserving the existing
archive pipeline and browser viewer.

## Scope

### In Scope

- A single long-running `agent` runtime entry point that owns startup refresh,
  viewer generation, localhost serving, and optional periodic incremental refresh.
- Per-user application-data locations for configuration, generated archive data,
  and logs so writable state is outside the installation directory.
- A non-interactive-friendly configuration bootstrap command that can create the
  per-user configuration without hand-editing YAML.
- Default configuration discovery that includes the per-user installed location
  while preserving explicit `--config` and development checkout behavior.
- Windows packaging scaffolding for a self-contained executable and per-user
  installer, including viewer web assets.
- Automatic launch at user logon from the installed package.
- Automated tests for portable runtime logic plus documented Windows smoke-test
  steps for build/install behavior that cannot be exercised on non-Windows CI.

### Out of Scope

- Notification-area/tray UI and browser settings (Phase 2 / REQ-DEPLOY-002).
- Code signing, managed defaults, enterprise update infrastructure, and endpoint
  management integration (Phase 3 / REQ-DEPLOY-003).
- A central multi-user server, cloud accounts, or synchronization.
- Running PowerPoint COM rendering from a Windows Service or Session 0.
- Replacing the existing SQLite/index/viewer pipeline.

## Required Behavior

1. Existing CLI commands keep accepting an explicit `--config` path and remain
   usable from a development checkout.
2. When no explicit config is supplied, the CLI checks the per-user application
   config location in addition to existing local development locations.
3. `pptviewer init-config` can create a usable configuration at the default
   per-user location, accepts one or more scan roots, creates the per-user archive
   directory, and refuses to overwrite an existing config unless explicitly
   requested.
4. The agent serves localhost promptly and performs the first scan/build in the background. It can periodically repeat incremental processing while the viewer remains available.
5. Refresh failures are logged and exposed through status/progress; the localhost server remains available even if the initial scan fails.
6. Windows packaging produces a self-contained application containing Python
   dependencies and the `web/` templates/static assets required by the builder.
7. The Windows installer installs per-user, launches the agent in the interactive
   user session at logon, and does not require administrator-only Windows Service
   installation.
8. User-writable configuration/archive/log data is not stored in the installed
   program directory.

## Acceptance Criteria

- [ ] A clean Windows user can install the application without Git or Python.
- [ ] The installer can initialize or preserve per-user configuration and arrange
  automatic user-logon startup.
- [ ] Starting the installed agent creates/uses the per-user archive, performs an
  incremental refresh, builds the viewer, and serves it on localhost.
- [ ] Periodic refresh can be enabled without restarting the server between scans.
- [ ] PowerPoint COM work executes in the signed-in user's process/session rather
  than a Windows Service.
- [ ] Existing explicit-config CLI workflows remain compatible.
- [ ] Automated portable tests pass for path discovery, configuration bootstrap,
  and agent lifecycle seams.
- [ ] A documented Windows smoke test verifies packaged build, install, logon
  launch, PPTX processing, and viewer access.

## Compatibility and Ownership

The existing `config.yaml` schema remains authoritative for runtime settings.
Phase 1 adds a per-user default location but does not migrate or silently rewrite
existing developer configs. Explicit `--config` always wins. Generated archive
state remains local and owned by the current Windows user.

On Windows the default application-data root is derived from the user's
`LOCALAPPDATA` environment. Non-Windows behavior keeps development/PDF-only use
working and provides a deterministic user-data fallback for tests and CLI use.

## Open Questions

- The final product display name/icon and signing identity are intentionally
  deferred; packaging should use a stable placeholder application identity that
  can be branded later without changing runtime data semantics.

## M004a — Cross-Platform Installer Preflight (2026-11-12)

- Run a dependency-light static preflight on any Python 3.10+ platform before attempting the Windows build; validate source inputs, both launchers, bundled viewer assets, PyInstaller requirements, per-user Inno Setup installer, startup/config preservation, and consistent release version defaults.
- Validate build.ps1 propagates native command failures and verifies the expected two executables and installer output. Optional artifact checks only inspect existing PE headers and file presence; no installer is executed.
- Produce a local JSON result with explicit pass/fail/warning and state that Windows PyInstaller, Inno Setup, logon startup, PowerPoint COM and uninstall smoke tests remain unverified.
- This does not sign builds, implement a Windows Service, or authorize enterprise rollout.
