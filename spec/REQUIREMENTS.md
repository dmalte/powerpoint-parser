# Requirements

This file is the stable product requirement inventory and backlog. Feature task
lists are implementation work and do not replace this inventory.

## Status Vocabulary

- `planned`
- `active`
- `implemented`
- `blocked`
- `deferred`
- `rejected`

## Archive and Processing

- [x] **REQ-ARCHIVE-001** — Scan configured roots recursively for supported presentation documents and maintain an incremental local archive index.
  - Status: implemented
  - Milestone: M001
  - Priority: high
  - Feature: historical implementation
  - Depends on: —
  - Validation: Existing scanner/index tests and successful incremental scans demonstrate new, changed, unchanged, and deleted-file handling.
  - Source: existing design and shipped behavior

- [x] **REQ-ARCHIVE-002** — Render and index PowerPoint slides on Windows and PDF pages on supported platforms.
  - Status: implemented
  - Milestone: M001
  - Priority: high
  - Feature: historical implementation
  - Depends on: REQ-ARCHIVE-001
  - Validation: Existing renderer/PDF processing tests plus representative scan runs.
  - Source: README, changelog, and current implementation

- [x] **REQ-ARCHIVE-003** — Support folder-scoped rescans without deleting or mutating indexed documents outside the requested scope.
  - Status: implemented
  - Milestone: M001
  - Priority: high
  - Feature: historical implementation
  - Depends on: REQ-ARCHIVE-001
  - Validation: Scanner regression tests cover scoped incremental behavior.
  - Source: existing design and README

## Viewer and Retrieval

- [x] **REQ-VIEWER-001** — Provide a generated local visual browser with search, filtering, thumbnails, previews, date navigation, and local slide starring.
  - Status: implemented
  - Milestone: M001
  - Priority: high
  - Feature: historical implementation
  - Depends on: REQ-ARCHIVE-001
  - Validation: Viewer generation tests plus manual browser verification.
  - Source: README and current implementation

- [x] **REQ-VIEWER-002** — Support advanced text retrieval including quoted phrases, multi-term AND behavior, and selectable search scopes.
  - Status: implemented
  - Milestone: M001
  - Priority: medium
  - Feature: historical implementation
  - Depends on: REQ-VIEWER-001
  - Validation: Search behavior tests or representative viewer checks.
  - Source: changelog and README

## Platform and Operations

- [x] **REQ-PLATFORM-001** — Keep PowerPoint COM rendering Windows-only while allowing installation and PDF-only use on Linux and other non-Windows platforms.
  - Status: implemented
  - Milestone: M002
  - Priority: high
  - Feature: direct maintenance work
  - Depends on: REQ-ARCHIVE-002
  - Validation: Dependency resolution succeeds without `pywin32` on non-Windows hosts; PDF workflows remain available; Windows keeps the COM dependency.
  - Source: current cross-platform packaging work

- [x] **REQ-OPS-001** — Maintain durable agent-managed development state using repository requirements, roadmap, living feature specs, validation gates, and a live handoff.
  - Status: implemented
  - Milestone: M003
  - Priority: high
  - Feature: repository infrastructure
  - Depends on: —
  - Validation: `python scripts/workflow_gate.py status` succeeds and workflow helper tests pass.
  - Source: repository workflow standardization

## Deployment and Distribution

- [ ] **REQ-DEPLOY-001** — Provide a Windows per-user packaged desktop agent that does not require Git, a separately installed Python runtime, virtual-environment setup, console startup, or manual YAML editing for normal operation. The installed agent must run in the signed-in user's session, own the local viewer server, support incremental refresh, use per-user application data, and be launchable automatically at user logon.
  - Status: active
  - Milestone: M004
  - Priority: high
  - Feature: specs/001-windows-desktop-agent
  - Depends on: REQ-ARCHIVE-001, REQ-ARCHIVE-002, REQ-VIEWER-001, REQ-PLATFORM-001
  - Validation: Automated tests cover installed-mode paths/config and agent lifecycle seams; a Windows build produces a self-contained executable and per-user installer; a Windows smoke test confirms logon launch and local viewer access without a development checkout.
  - Source: accepted three-phase deployment plan, 2026-08-18

- [ ] **REQ-DEPLOY-002** — Add a self-service desktop experience for the installed agent, including tray controls for archive status, opening the archive, scanning now, settings, logs, restart, and exit, plus browser-based configuration of scan folders and refresh behavior.
  - Status: active
  - Milestone: M005
  - Priority: high
  - Feature: specs/002-self-service-controls
  - Depends on: REQ-DEPLOY-001
  - Validation: Representative user flows can be completed without a console or direct configuration-file edits.
  - Source: accepted three-phase deployment plan, 2026-08-18

- [ ] **REQ-DEPLOY-003** — Make Windows distribution enterprise-ready with code signing, unattended installation support, managed/default settings, version and diagnostics surfaces, and an update/distribution path suitable for company software management.
  - Status: planned
  - Milestone: M006
  - Priority: medium
  - Feature: not selected
  - Depends on: REQ-DEPLOY-001, REQ-DEPLOY-002
  - Validation: Signed release artifacts support silent deployment and diagnostics/version verification in a managed Windows environment.
  - Source: accepted three-phase deployment plan, 2026-08-18

## Performance and Scale

- [ ] **REQ-PERF-001** — Keep the local viewer responsive for archives containing at least 6,000 indexed slides/pages on representative company Windows laptops, with measured performance budgets for initial load, filtering/search, sorting/grouping, scrolling, and thumbnail/preview loading. The implementation should avoid creating DOM nodes for the entire archive at once and should preserve local-first operation.
  - Status: planned
  - Milestone: M007
  - Priority: medium
  - Feature: not selected
  - Depends on: REQ-VIEWER-001, REQ-DEPLOY-002
  - Validation: A reproducible 6,000-slide benchmark fixture records exported-data size, initial interactive time, filter/search latency, DOM node/card count, memory behavior, and image-serving behavior on a representative Windows laptop; acceptance budgets are finalized in the future feature spec before implementation completion.
  - Source: large-archive performance planning, 2026-08-18

## Backlog

Add accepted requirements here using stable IDs. Do not renumber existing IDs. Substantial new behavior should be linked to a numbered `specs/<feature>/` record before implementation.
