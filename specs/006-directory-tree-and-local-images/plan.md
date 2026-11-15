# Plan

- Add a dependency-free client-side tree/filter module. Construct a trie once from existing deck paths. Efficiently compute recursive counts, and render expanded nodes and search matches on demand. Viewer-only state uses include/exclude path Sets, canonical forward-slash separators and exact-segment descendant matching. No server API or DB migration.
- Add folder search, include/exclude and clear-selection controls next to current Folders sidebar, replacing its flat exact-match list. Connect to active tags and deck-selection reset.
- Extend safe MarkdownIt image rendering with a per-document image resolver. Copy only whitelisted decoded source images into current ImageGeneration staging directory, strip metadata on re-encode, and use safe basename relative image links. Set CSP to permit same-origin copied images for offline assets, while maintaining no script/network. With sandbox iframe, verify image origin behavior.
- Bound image files, pixels and per-document count. Image-dependent markdown signatures must invalidate old previews after renderer update without forcing PPTX/PDF to reprocess.
- Run Pi pytest/JS and a browser smoke, synchronize clean Mac1 checkout through Pi federation, run native tests, rebuild arm64 app, and upgrade using staged installer with verified backup and scan-state preservation. Use snapshot/viewer publication without unnecessarily restarting multi-thousand-file scan.

## Implementation details and limitations

- A pure JS trie builds once from published decks, aggregates recursive documents and slides, and renders only expanded/search-matching nodes with 360-row cap. Include/exclude rules are in-session only; exact path-segment boundaries prevent sibling prefix collisions; exclusions win. No indexing exclusions or saved views yet.
- Markdown previews use a Pillow decoder and bounded resolver for relative and vault-root-relative image paths; sources must remain in configured scan roots. Up to 48 images per note, 12 MiB each, 64 MiB cumulative, 16 MP source; output downscaled to 2048 px and re-encoded JPG/PNG without original metadata. GIF first frame only. SVG/data/remote/missing/malformed and outside-root symlinks become inert placeholders.
- Embeds using Obsidian image form are normalized outside fenced code blocks. Vault fallback is only available with a .obsidian ancestor and an explicit path, not basename search or note-opening deep links.
- Markdown preview images share the immutable deck generation; scripts/forms/network remain blocked by restrictive CSP, with same-origin images permitted inside a no-script sandbox iframe. Old MD signatures get a renderer version suffix to reprocess them at next scan. Image-only edits do not yet trigger rerender without touching the Markdown file.
- Pi tests, Node subtree tests and headless Chromium synthetic startup/interaction pass. Native Mac acceptance and large-library safe deployment remain pending.

## Native Mac1 deployment and validation (2026-11-14)

- Clean Pi commit a880e1a fast-forwarded into Mac1, preserving three pre-existing generated egg-info modifications (no overlapping files); Mac1 full repository suite 170/170, six non-failing dependency warnings.
- Isolated native Markdown source scan rendered both ordinary relative and Obsidian vault-path embedded images in two snippets, verified offline HTML/CSP, HTTP image response and unchanged source checksums. Isolated packaged CLI also scanned and built a Markdown note with a local image.
- Arm64 .app and CLI rebuilt, 17/17 packaging checks and strict ad hoc codesign verification passed. Staged installer upgraded the existing per-user app while preserving all configured scan roots, enabled PPTX/PDF/MD types, SQLite and historical asset generations.
- Before upgrade, user agent was paused and source YAML/SQLite backed up and verified: 14,166 active decks / 141,843 slides/snippets (10,254 Markdown decks). Installed app hash matched rebuilt bundle; localhost viewer served tree UI, new JS and type controls. Prior unpaused preference was restored via Resume and scan was accepted.
- Existing Markdown file signatures are intentionally invalidated once; agent reported 10,331 files queued for the next incremental reprocessing pass, which was still running when checked. Existing published archive remains browseable until another checkpoint/completion. Large-library completion and individual source conversion errors are not part of this feature acceptance.
- Pi real DOM browser test clicked folder exclude/clear and typed folder search in headless Chromium; all operations passed, with 120 synthetic slides and no JS errors.
