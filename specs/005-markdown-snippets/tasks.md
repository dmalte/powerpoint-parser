# M009 — Markdown Visual Snippets

- [x] T010 Add safe Markdown parsing, heading section splitting and preview/thumbnail generation.
- [x] T011 Index Markdown snippets through existing immutable asset/SQLite pipeline; preserve prior records on failure.
- [x] T012 Enable .md in persisted configuration, Settings and viewer filters; show rendered HTML preview safely.
- [x] T013 Test security, mixed scanning, incremental updates, rollback and viewer rendering.
- [x] T014 Update consolidated docs and handoff; run full tests and commit locally (Pi: 161 tests; static Windows and Mac preflights pass).
- [x] T015 Mac1 fast-forwarded/verified, full 161-test suite passed, arm64 app rebuilt (17/17 preflight), packaged CLI and isolated Markdown/PDF scan passed; installed upgrade preserved existing config and database, and .md remains opt-in.

## Future M010 — Obsidian Vault Navigation

- [ ] Discover vault from nearest .obsidian ancestor and distinguish vault name/collisions.
- [ ] Double-click Markdown snippet opens the correct note/section in Obsidian via a canonical local link.
- [ ] Fall back to OS default file handler, validate URI escaping, missing app and no untrusted link execution.
