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
