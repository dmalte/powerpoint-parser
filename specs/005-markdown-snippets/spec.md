# Markdown Visual Snippets

- Feature: specs/005-markdown-snippets
- Milestone: M009
- Requirements: REQ-MD-001
- Status: done (portable and Mac1 native acceptance passed)

## Goal
Index user-selected .md files into the same local visual archive as PPTX/PDF. Treat headings (and long heading-free content chunks) as individually searchable, rendered snippets. Each snippet has a lightweight JPEG thumbnail, safe offline HTML preview, text and a way to open original Markdown.

## Acceptance
- Configurable md file type, including Settings checkbox, filter and incremental signatures.
- Sections split on headings outside fenced code blocks; long heading-free sections split at paragraphs. Original source unchanged; YAML frontmatter does not render as content.
- Offline rendering supports common Markdown headings, emphasis, lists, tables, fenced code and blockquotes. No executable/raw HTML or remote resources.
- Each snippet becomes a Slide row without schema change, with its own JPEG thumbnail and HTML preview published via ImageGeneration. Failed reprocessing preserves old rows/assets.
- Existing PPTX/PDF behavior, incremental scanning, pause/resume and immutable generations unaffected.
- Existing original-file open action supports Markdown. Obsidian vault-aware double-click navigation is a separate M010 milestone.

## Security and limits
- Rendered HTML is inert with restrictive CSP; no raw HTML, scripts or remote resources from Markdown.
- Local/remote images are rendered as alt-text placeholders for now; packaging local images and Obsidian wikilinks may be added later.
- A small CommonMark parser is preferred to brittle homegrown parsing; dependency rationale documented.
