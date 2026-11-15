# Directory Tree Filtering and Local Markdown Image Fidelity

- Feature: specs/006-directory-tree-and-local-images
- Milestone: M011
- Requirements: REQ-DIR-001, REQ-MD-IMG-001
- Status: active

## Accepted behavior
- Viewer sidebar has a collapsible, searchable directory tree derived from indexed folder paths (not scan roots); show recursive document/snippet counts and type-to-find path search.
- Users can include multiple parent directories and exclude directories within those selections. Matching is recursive and boundary-aware, excludes take precedence. With no inclusions, show all except exclusions.
- Folder filters compose with filename, slide/section search, file type, time, stars, pagination and modal navigation; clearable individual chips and one-click reset. No SQLite schema/index or ingestion configuration changes.
- Display only expanded branches or matching search ancestors; do not create a DOM entry for thousands of collapsed nodes.
- Markdown image references in preview render from copied, safe local image assets inside the same immutable snippet generation. Respect relative paths and user's selected scan roots; reject remote URLs, absolute paths, unsafe symlinks, missing/invalid/huge images. Do not read beyond configured scan roots. Allow JPEG/PNG/WebP/GIF decoded by Pillow and re-encoded to inert PNG/JPEG; SVG and raw HTML never load. Missing/unsafe sources show escaped alt-text placeholders.
- Existing source Markdown, input images, PDF/PPTX renderers, SQLite rows and old published asset generations are unchanged. CSP and iframe isolation still block scripts, network requests and arbitrary navigation.
- Obsidian vault-aware links/opening and unbounded vault-wide attachment lookups are M010, not part of this change.

## Acceptance
- Pure path/tree tests: POSIX+Windows separators, parent/child boundaries, includes/excludes, search ancestors, recursive aggregates, dense-tree performance.
- Browser test click-to-expand, include/exclude, search and combined filters on synthetic archive, with no malformed DOM or unsafe HTML insertion.
- Markdown tests: relative assets, encoded filenames, nested path inside scan roots, traversal outside roots, symlinks, remote/data/SVG, over-size/corrupt file, original bytes, referenced image served on loopback, and no-script no-network restrictions.
- Native Mac1 build/upgrade only after portable tests; preserve ongoing production scan and archive database; no unapproved origin push.

## Explicit limits

- Directory include/exclude rules affect only current viewer results; saved views and ingestion exclusions remain separate.
- Obsidian image paths require explicit relative paths; vault opening/automatic attachment basename search are future M010 work.
- Markdown signature version causes a one-time re-render of old previews; changing only the referenced image does not automatically trigger reindexing.
