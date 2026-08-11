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

## Backlog

Add accepted requirements here using stable IDs. Do not renumber existing IDs. Substantial new behavior should be linked to a numbered `specs/<feature>/` record before implementation.
