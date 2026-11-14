# Markdown Visual Snippets — Plan

## Architecture
- New markdown_processor with markdown-it-py CommonMark parser, raw HTML disabled, linkify disabled, tables enabled; group markdown on headings outside fences and split long sections.
- Preview: per-snippet complete HTML file with restrictive CSP and inline CSS, displayed inside a sandboxed iframe only when clicked (never execute Markdown as JS).
- Thumbnail: Pillow-generated JPEG from heading and excerpt. It is a readable thumbnail, not a pixel screenshot of the HTML preview.
- Pipeline: one Markdown deck uses existing ImageGeneration and Deck/Slide SQLite transactions, no schema change. md opt-in through config and Settings. Viewer adds MD filter and HTML modal preview.
- Existing index/export stays compatible with PPTX/PDF; no source mutation or remote image retrieval.
- Package markdown-it-py as production parser dependency and rebuild Mac1 native app after portable validation.
- Obsidian M010 later: recognize nearest ancestor .obsidian, build canonical vault-relative open link and optional heading anchor, fallback to OS default. No arbitrary untrusted URL execution.

## Tests
- Section boundaries/headings/fences/frontmatter/long sections/tables/code/security.
- Mixed Markdown/PDF scan, SQLite/JSON, HTML preview and JPEG thumbnail, changed file and failure rollback, pause/resume.
- Portable tests and native Mac1 isolated reference acceptance; do not alter production source folders or types.

## Mac1 native acceptance (2026-11-14)

- Fast-forwarded clean Mac1 to 891852e, installed markdown-it-py 4.3.0 in its development virtualenv, and passed all 161 Mac1 tests.
- Isolated native source scan: two Markdown notes plus one PDF, three decks and five section/page records; validated four HTML snippets/JPEG thumbnails, offline CSP, original source hashes unchanged and HTTP preview served.
- Rebuilt Mac arm64 app/CLI with markdown-it parser included; native package preflight 17/17, strict ad hoc code-signature verification successful. Packaged CLI independently scanned an added Markdown note as two formatted sections and regenerated viewer successfully.
- Backed up user YAML and SQLite before upgrading. Staged native app/CLI installer preserved the existing two scan roots, PPTX/PDF types, unpaused preference and source index. Installed binary matched rebuilt artifact.
- Viewer was deliberately checkpointed during the 1,015-file incremental run, exposing the new Markdown checkbox/filter. The agent was resumed to preserve prior preference; Markdown remains disabled in production until opted in. Published snapshot at checkpoint: 3,575 decks and 18,040 slides/pages.
- Scanner skipped one verified vanished source file and deferred deletion reconciliation rather than aborting; other per-file errors (including encrypted/corrupt PDFs and PowerPoint conversion failures) remain independent cleanup work.
