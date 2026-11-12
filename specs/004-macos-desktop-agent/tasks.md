# Tasks — macOS Desktop Agent Preparation

- Feature: specs/004-macos-desktop-agent
- Milestone: M008
- Requirements: REQ-MAC-001

## Preparation
- [x] T001 Establish Mac scope and pass feature workflow gate.

## Rendering
- [x] T010 Implement Mac PowerPoint AppleScript temporary PDF converter and shared rasterized slide images with timeout/cleanup.
- [x] T011 Add explicit LibreOffice backend and platform factory; keep Windows COM unchanged.
- [x] T012 Tests for metadata/search parity, renderer failures, conversion and cleanup.

## Local UX and Packaging
- [x] T020 Add macOS per-user paths, Finder open/reveal and tests.
- [x] T021 Add Mac LaunchAgent and build/install scaffolding plus static preflight.

## Validation
- [x] T030 Run full Pi tests and mock-converter integration.
- [x] T031 Update README/design/requirements/roadmap/changelog/handoff; inspect diff and commit locally.
- [ ] T032 Real macOS PowerPoint, packaging, permissions, fidelity, login validation pending.
