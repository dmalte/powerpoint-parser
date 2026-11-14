# Roadmap

This file defines outcome-level milestones and delivery order. A milestone may span multiple chats and, when useful, multiple features.

## Status Vocabulary

- `planned`: accepted but not currently selected
- `active`: currently being implemented
- `paused`: intentionally stopped but not abandoned
- `blocked`: cannot proceed until a dependency is resolved
- `done`: validated and documented
- `deferred`: accepted for later reconsideration
- `rejected`: explicitly not planned

## Milestones

| ID | Milestone | Outcome | Depends on | Status | Feature |
|---|---|---|---|---|---|
| M001 | Local visual archive foundation | PowerPoint/PDF documents can be indexed incrementally and browsed through the generated local viewer with search and retrieval tools | — | done | historical implementation |
| M002 | Cross-platform packaging | Non-Windows hosts can install the project for PDF-only workflows without requiring `pywin32`, while Windows retains PowerPoint COM rendering | M001 | active | direct maintenance work |
| M003 | Agent-managed development workflow | Repository work is governed by durable requirements, roadmap, living feature records, workflow gates, and a current handoff | M001 | active | repository infrastructure |
| M004 | Phase 1 — Windows packaged desktop agent | Colleagues can install a per-user Windows build that runs in the signed-in user session, owns the local archive server, refreshes incrementally, and starts at logon without Git/Python/console setup | M001, M002 | paused | specs/001-windows-desktop-agent |
| M005 | Phase 2 — Self-service desktop experience | Installed users can control status, scanning, settings, logs, restart, and archive opening through tray/browser UI without editing YAML or using a console | M004 | paused | specs/002-self-service-controls |
| M006 | Phase 3 — Enterprise distribution | IT can distribute signed builds silently with managed defaults, diagnostics/version visibility, and a company-suitable update path | M005 | planned | not selected |
| M007 | Large-archive viewer and ingestion performance | Profile and keep viewer interactions responsive at 6,000+ slides/pages while measuring scan/processing time using locally exportable diagnostics and bounded rendering | M005 | active | specs/003-large-archive-performance |
| M008 | macOS desktop agent preparation | Prepare shared viewer with macOS PPTX rendering, Finder actions, per-user data paths and per-user packaging; Mac native acceptance pending | M001, M002 | active | specs/004-macos-desktop-agent |
| M009 | Markdown visual snippet indexing | Index .md documents as safe offline HTML preview sections with searchable thumbnail cards in the same archive | M001, M008 | active | specs/005-markdown-snippets |
| M010 | Obsidian-aware note opening | Recognize vault membership and open a Markdown snippet at the corresponding note/section on double click, with OS open fallback | M009 | planned | future feature |

M007 is high priority for release readiness. Browser and scan/build hooks, local reporting, a repeatable 6,000/20,000-slide benchmark harness, and background-startup progress were implemented and validated on Pi. M007c now skips unchanged viewer builds when a complete marker matches source assets, and stages JSON/HTML/CSS/JS before atomic file swaps. A one-page PDF probe completed a first build in ~440 ms and repeated no-change refreshes in ~5–6 ms on Pi. Synthetic browser reference data: 6,000 slides ~953 ms interactive / 131 ms p95 filter-to-grid; 20,000 slides ~1,377 ms / 195 ms, with no more than 240 cards. These are **not** Windows acceptance figures; Windows performance acceptance remains open. M004/M005 package acceptance is still paused until representative Windows testing.

M007d comparison tooling now produces an offline performance-history HTML dashboard and machine-readable warnings from compatible clean-revision runs. It deliberately excludes different browser builds/machines/input shapes and p95s based on fewer than five observations. Real hardware performance acceptance remains pending.

M007e now protects indexed data against disconnected scan roots, unreadable input, changed-document processing errors and a crash after SQLite commit but before viewer publishing. It includes fault-injection tests for disk space and SQL rollback. This does not prove COM/media recovery on Windows.

M004a portable packaging preflight is implemented: source consistency, conditional COM dependency, user-scoped startup/config preservation, version alignment, build error propagation and optional PE header checks. This does not change M004's paused Windows installer acceptance status.

M007f targets measured grid-rendering overhead, preserving the existing JSON search architecture and 240-card page bound. Pi synthetic 50,000-slide stress completed with ~106 MiB JSON, ~237–239 MB JS heap and ~1.8–2.1 s initial readiness; this does not validate real thumbnail or Windows behavior. Clean-revision Pi comparison (7cc0da7 → 03fc5f4) measured grid p95 improvements of ~19% at 6,000 slides and ~54% at 20,000, with filter-to-grid p95 improvements of ~19% and ~24% respectively; all are synthetic one-run measurements and should be repeated on Windows.

M008 macOS work is now prepared on the Pi: renderer selection, AppleScript PowerPoint-to-ephemeral-PDF-to-image pipeline, explicit LibreOffice option, Finder integration, native application-data paths, and source packaging/install preflight. Native PowerPoint AppleScript, macOS Automation consent, app bundle build, and LaunchAgent login tests remain unchecked. Windows COM and archive output format are unchanged.

M008a–d source work is implemented and Pi-tested: immutable per-deck image generations with SQLite rollback safety, data-preserving staged macOS upgrades/uninstall, path-free readiness diagnostics, and original PowerPoint reference decks with offline per-slide image comparison. User-session permissions, macOS bundle/launchctl and true PowerPoint visual fidelity remain native acceptance gates. Older image versions are retained deliberately until a safe cleanup policy is defined.

M008 native Mac checkout and app build were validated on Mac1: 132 portable tests, 17/17 artifact checks, signed-by-PyInstaller ad hoc arm64 bundle, packaged CLI PDF indexing/HTML viewer, and app localhost startup/shutdown. Native PowerPoint 16.115 PDF automation returned -9074; direct AppleScript JPG output remains unverified. M008 stays active pending unlocked user-session automation/file access and visual comparison. Login-agent installation has not been performed.

M008e addresses a confirmed Mac PDF limitation: hidden slides were excluded (5 of 6 pages). The renderer now temporarily unhides only the private PPTX copy before export; portable regression tests verify source preservation, full slide order and notes. Native Mac interactive acceptance now passes for all six slides (12 validated JPEG files), including the hidden final slide; original PPTX checksum and slide notes remain intact. A two-slide PowerPoint-for-Mac rendering test passed under the signed-in Terminal, but the system MCP daemon's GUI automation remains unreliable.

M008f addresses native macOS file-access prompts during production-size scanning. The Mac PowerPoint renderer now stages its ephemeral PPTX/PDF inside PowerPoint's own Documents container, instead of a unique external archive path per file. User consent may still be required once for the archive app to access the Office container. Pi regression suite passed (140 tests). Mac arm64 build passed 17/17 packaging checks, but a dedicated isolated user LaunchAgent failed both synthetic PPTX conversions with PowerPoint -9074 despite sandbox staging. The test agent was removed; production auto-start remains disabled. Terminal-versus-background automation acceptance and safe restart of the 3,952-file archive remain pending.

M008f native retry evidence (2026-11-12): after one Terminal failure and one isolated gui/501 LaunchAgent failure with PowerPoint -9074, the next Terminal run passed (2/2) and a new isolated LaunchAgent passed two reference decks followed by four additional uniquely named synthetic PPTXs (6 decks, 24 slides, 0 errors). The per-user test agent was removed and production autostart remains held. The app cannot read macOS permission dialogs, so file-by-file prompt elimination is not yet accepted without user confirmation.

M008g native Mac1 acceptance completed: upgraded per-user app with config and SQLite preserved, published the real partial index (2,959 decks / 15,809 slides), and confirmed paused startup and viewer controls. Separate GUI user agent verified 4-file Resume/Pause and restart persistence; production remains paused until user action. Conventional notarized distribution and pixel-level visual parity remain separate work.

M008g implements pause/resume during long scans and a browsable partial checkpoint. Cooperative per-file stopping preserves committed SQLite/image generations, defers deletions until a complete pass, and publishes HTML/JSON from the current index. User pause survives restart/login and disables scheduled scans; Resume reruns incremental signature detection and skips previously processed unchanged decks. Buttons are in both viewer and Settings, with loopback control APIs and numeric status. Portable Pi tests passed; Mac1 package deployment and real partial-library acceptance are still required.

M009 Markdown visual snippets are implemented in source: opt-in .md scanning, safe offline MarkdownIt-rendered HTML section previews, Pillow JPEG thumbnail cards, search/filter and original-file actions, using existing SQLite/immutable asset generations. Portable regression tests cover injection, rollback, mixed Markdown/PDF, incrementality and disappearing files. Mac1 native acceptance and packaging update remain in progress. M010 Obsidian vault discovery/deep-link double-click remains planned.

## Deployment Sequence

The accepted rollout is intentionally staged:

1. **Phase 1:** package the existing local-first application as a per-user Windows desktop agent and installer. Keep PowerPoint COM automation in the interactive user session rather than a Windows Service.
2. **Phase 2:** add tray controls and browser-based settings so normal operation and troubleshooting are self-service.
3. **Phase 3:** add signing, unattended deployment, managed defaults, diagnostics, and update/distribution support for company-wide rollout.

## Next Development Selection

`specs/003-large-archive-performance` is the selected substantial feature for M007 / REQ-PERF-001. M004 and M005 implementations remain paused only for their pending packaged Windows acceptance checks; the operator explicitly requested continuing into M007 before those smoke tests.

## Notes

- Add milestones only for meaningful outcomes, not for every chat.
- Link an active substantial milestone to its selected `specs/<feature>/` directory.
- Direct maintenance may remain featureless when behavior is already defined and localized.
- Keep completed milestones as history.
