# Implementation Plan: Windows Packaged Desktop Agent

- Feature: `specs/001-windows-desktop-agent`
- Milestone: M004
- Requirements: REQ-DEPLOY-001

> Living document: update this file whenever the actual implementation approach,
> component responsibilities, data flow, compatibility handling, validation
> strategy, affected files, or implementation phases change materially.

## Current Context

The application is a Python CLI with an incremental scanner, SQLite index, static
viewer builder, and localhost HTTP server. PPTX rendering uses Microsoft
PowerPoint COM on Windows; PDF processing is cross-platform. The current user
workflow assumes a development checkout, a Python environment, a manually edited
`config.yaml`, and separately invoked `scan`, `build`, and `serve` commands.

The existing builder resolves `web/` assets relative to the source tree, so a
packaged executable must explicitly bundle those assets. The renderer already
initializes COM in the thread that performs PPTX work, which allows scheduled
refresh work to remain in the interactive per-user agent process.

## Approach

Introduce a thin installed-runtime layer without replacing the archive core:

1. Centralize per-user application paths in a small platform-path module.
2. Extend config discovery and add `init-config` so installers/users can bootstrap
   a config without editing YAML.
3. Add an agent controller that performs initial scan/build, starts the existing
   localhost server, and runs optional periodic incremental scan/build cycles in a
   background thread.
4. Make web-resource discovery compatible with both source installs and PyInstaller.
5. Add Windows build/installer definitions: PyInstaller for the self-contained
   executable and Inno Setup for a per-user installer/start-at-logon shortcut.
6. Validate portable behavior in pytest and leave explicit Windows smoke checks for
   executable/installer/PowerPoint integration.

No new runtime dependency is required for the agent controller. PyInstaller is a
build-time development dependency; Inno Setup remains an external Windows build
tool rather than a Python runtime dependency.

## Components and Responsibilities

- `platform_paths.py`: derive per-user config/data/log paths; no business logic.
- `config.py`: serialize/bootstrap config using the existing schema.
- `cli.py`: preserve existing commands; add installed config discovery,
  `init-config`, and `agent` commands.
- `agent.py`: lifecycle orchestration for initial refresh, periodic refresh, and
  server ownership.
- `server.py`: expose a server construction/run seam that can coexist with the
  agent scheduler while preserving `serve`.
- `builder.py`: resolve packaged `web/` resources correctly.
- `packaging/windows/`: PyInstaller spec/build helper and Inno Setup installer.
- `tests/`: focused unit tests for path/config/agent behavior without requiring
  Windows COM.

## Data Flow and Persistence

Default installed state:

```text
%LOCALAPPDATA%/PowerPointVisualArchive/
  config.yaml
  archive/
    data/index.db
    data/export.json
    index.html
    assets/...
  logs/
```

`init-config` writes the config atomically enough for normal local use and does
not overwrite an existing file without `--force`. The config continues to own
scan roots, file types, rendering settings, and processing behavior. The agent
creates derived archive state through existing pipeline/builder code.

## Affected Areas

- Application components: CLI, config, server, builder, new agent/path modules.
- Persistence: default location only; schema remains YAML + SQLite as today.
- User interfaces/APIs: new CLI commands; existing viewer HTTP behavior unchanged.
- Build/distribution: PyInstaller bundle and Inno Setup script.
- Tests: portable unit/lifecycle coverage and Windows smoke-test documentation.
- Documentation: README, design spec, requirements, roadmap, changelog, handoff.

## Compatibility and Risk

- Explicit `--config` remains highest-priority and source-tree config discovery is
  retained, preventing breakage for current users.
- Do not make `pywin32` unconditional; Linux/PDF-only installs must still resolve.
- PowerPoint automation stays inside the signed-in user's agent process.
- Scheduled refresh runs concurrently with HTTP serving but refresh operations are
  serialized to one scheduler thread; no overlapping scans are introduced.
- Updating generated viewer files while the HTTP server is serving may briefly
  expose a file during replacement, matching the existing local-build semantics;
  atomic publishing can be considered separately if observed in practice.
- PyInstaller resource paths differ from source layouts, so builder resource lookup
  must be tested using an injectable/frozen-path seam.
- Windows packaging cannot be fully validated on the current non-Windows host.

## Implementation Phases

1. **Runtime foundation:** per-user paths, config bootstrap/discovery, agent
   controller, packaged-resource lookup, focused tests.
2. **Windows packaging:** PyInstaller build definition and Inno Setup per-user
   installer with Start Menu shortcut and user-logon startup.
3. **Validation/convergence:** portable full tests, Windows smoke-test procedure,
   README/changelog/handoff reconciliation; mark M004 done only after Windows
   smoke validation.

## Validation

Portable automated checks:

- path derivation with controlled environment variables;
- `init-config` serialization, directory creation, and overwrite protection;
- config-resolution precedence;
- agent initial refresh ordering and periodic refresh failure isolation using
  injected callables/events;
- packaged web-resource path selection;
- existing full pytest suite.

Windows acceptance checks:

- build PyInstaller artifact on Windows;
- compile Inno Setup installer;
- install as a standard user;
- confirm no Python/Git prerequisite;
- initialize config/scan roots;
- confirm logon-start entry launches the agent in the user session;
- process at least one PPTX through PowerPoint COM;
- open `http://127.0.0.1:8080` and exercise open-file/open-folder actions.

## Documentation Convergence

Update throughout the feature:

- `spec/DESIGN_SPEC.md` for stable deployment architecture;
- `spec/REQUIREMENTS.md` for REQ-DEPLOY-001 status;
- `ROADMAP.md` for M004 status;
- `README.md` for installed and developer workflows;
- `CHANGELOG.md` after validated runtime/packaging behavior exists;
- `dev/HANDOFF.md` after each meaningful implementation/validation step.
