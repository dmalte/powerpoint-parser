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

- [ ] **REQ-PERF-001** — Keep the local viewer responsive for archives containing at least 6,000 indexed slides/pages on representative company Windows laptops, with measured performance budgets for initial load, filtering/search, sorting/grouping, scrolling, and thumbnail/preview loading; also collect aggregate scan, per-format processing, and archive-export timings locally with a path-free, user-downloadable diagnostics report. The implementation should avoid creating DOM nodes for the entire archive at once and should preserve local-first operation.
  - Status: active
  - Milestone: M007
  - Priority: high
  - Feature: specs/003-large-archive-performance
  - Depends on: REQ-VIEWER-001, REQ-DEPLOY-002
  - Validation: Local browser timing hooks (including download) and backend scan/build metrics have automated and headless Chromium coverage with a 6,000-slide synthetic archive. Representative Windows initial-interactive, filter/search, scroll, image and memory acceptance measurements and budgets remain outstanding.
  - Source: large-archive performance planning, 2026-08-18
  - Portable verification: Synthetic, revision-tagged Chromium benchmarks at 6,000/20,000 slides and nonblocking first-run HTTP/scan progress checks are implemented (2026-11-12). M007c tests verify no-op publishing and concurrent readers; M007d compares two clean matching benchmarks; M007e now tests missing mounts, I/O/permission errors, corrupt PDFs, transactional deck rollback, interrupted export and disk-full recovery. M007f additionally reduces repeated date formatting and releases stale image observers; comparable clean-revision Pi benchmarks showed improved grid/filter latency at 6K/20K synthetic slides. Real Windows and image/COM acceptance remain pending.

## macOS Preparation

- [ ] **REQ-MAC-001** — Prepare a macOS user-session archive with PowerPoint automation yielding Windows-compatible slide JPEG/text assets, optional LibreOffice rendering, native Finder open/reveal, per-user paths and login/build scaffolding.
  - Status: active (portable Pi implementation/tests pass; native macOS acceptance pending)
  - Milestone: M008
  - Priority: high
  - Feature: specs/004-macos-desktop-agent
  - Depends on: REQ-ARCHIVE-001, REQ-ARCHIVE-002, REQ-PLATFORM-001
  - Validation: Mac1 built arm64 app/CLI (17 artifact preflight passes), indexed a real PDF and ran the packaged HTTP viewer. Interactive Terminal PowerPoint exported 2/2 images, but a six-slide reference deck exported only five because its hidden slide was skipped. The M008e private-copy fix passed native Mac validation: 6/6 slides, 12 valid JPEG files, correct title/notes mapping, unchanged original PPTX checksum and hidden flag. Per-user LaunchAgent/login, Windows/Mac pixel fidelity and distribution signing remain outstanding.
  - Sandbox-permission status: M008f Pi-tested Mac temporary PPTX/PDF staging inside Microsoft PowerPoint's container. Native Mac1 retry passed 6 synthetic decks / 24 slides / 0 errors in an isolated GUI LaunchAgent after prior intermittent -9074 failures. Repeated permission-dialog elimination is not yet independently confirmed by the user; production 3,952-file LaunchAgent remains safely disabled pending staged resumption.
  - Partial-archive controls: M008g adds Pause Scan & Save and Resume Scan in local viewer/Settings, persisted pause across app restarts, incremental resume and a durable HTML/JSON snapshot of committed decks. Partial scans must never infer deletions. Pi validation passes; Mac1 production-package acceptance pending.
  - M008g native acceptance: Mac1 installed upgraded arm64 app preserving config/SQLite and published 2,959 decks / 15,809 slides; paused startup confirmed. Separate 4-PDF GUI LaunchAgent resumed, paused, saved and retained pause across restart. Production remains paused for explicit user control.
  - Source: macOS desktop preparation request, 2026-11-12

## Markdown archive extension

- [x] **REQ-MD-001** — Index .md files as heading-level visual snippets with safe offline HTML previews, searchable text, lightweight thumbnails, and original-file opening alongside PPTX/PDF.
  - Status: done, M009; native Mac1 and portable suite passed, .md opt-in
  - Validation: 12 Markdown parsing/rendering/index/UI tests and 3 vanished-source safety tests pass; full 161-test suite passed on Pi and Mac1. Native Mac1 packaged CLI/installed app, HTML preview/thumbnail/CSP and preserved production config verified; M010 Obsidian vault navigation remains planned.
  - Feature: specs/005-markdown-snippets
  - Depends on: REQ-ARCHIVE-001, REQ-ARCHIVE-002
  - Security: No executable HTML, remote resources, source mutation or untrusted URL execution. Existing archive schema and incremental safety retained.

- [ ] **REQ-OBSIDIAN-001** — Open Markdown indexed within local Obsidian vault at its note/section on double click, with a safe OS file-open fallback.
  - Status: planned for M010; not included in M009
  - Depends on: REQ-MD-001

## Backlog

Add accepted requirements here using stable IDs. Do not renumber existing IDs. Substantial new behavior should be linked to a numbered `specs/<feature>/` record before implementation.
