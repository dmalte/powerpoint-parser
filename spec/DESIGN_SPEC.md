# Design Spec

## Goal

Build a local-first PowerPoint and PDF visual archive for fast slide/page discovery without opening large source files. The app scans one or more folders, exports slide/page imagery, extracts lightweight metadata, stores it in SQLite, and generates a local HTML viewer optimized for visual retrieval.

## Product Boundaries

In scope:
- Recursive `.pptx` and `.pdf` scanning across multiple roots
- Incremental change detection by path, file size, and modified timestamp
- Slide/page thumbnail and preview export
- PowerPoint slide and PDF page metadata extraction
- Static HTML viewer with local filtering and search
- Windows-first local file opening via the optional built-in server
- PDF-only installation and use on non-Windows platforms

Out of scope:
- Editing PowerPoint files
- Cloud sync, accounts, or collaboration
- OCR, semantic search, or AI-heavy indexing
- Browser upload flows

## Locked Decisions

- PowerPoint rendering source: Microsoft PowerPoint COM automation on Windows
- PDF rendering and text extraction: PyMuPDF
- PowerPoint metadata extraction: `python-pptx`
- Persistent index: SQLite
- Viewer architecture: static HTML/CSS/JS generated from indexed data
- Activity date semantics: deck file modified time
- Incremental behavior: unchanged decks are skipped; changed decks are fully rebuilt
- Scoped rescans: selected folders can be rescanned without affecting decks outside the chosen scope

## Architecture

Pipeline:
1. Scan configured roots for enabled `.pptx` and `.pdf` file types
2. Detect new, changed, unchanged, and deleted documents
3. Export PowerPoint slide imagery via COM on Windows or PDF page imagery via PyMuPDF
4. Extract structured text and metadata with the format-specific processor
5. Upsert documents and slides/pages into SQLite
6. Export JSON and render the static viewer

Runtime surfaces:
- CLI for `scan`, `build`, `serve`, `clean`, and `rebuild`
- Optional local HTTP server for browser-safe "open original" and "open folder" actions
- Static frontend for search, filters, heatmap, preview modal, and starring slides

## Data Model

### Deck
- `deck_id`
- `file_path`
- `file_name`
- `folder_path`
- `file_size`
- `modified_time`
- `processed_time`
- `slide_count`
- `file_signature`
- `status`

### Slide
- `slide_id`
- `deck_id`
- `slide_number`
- `title`
- `subtitle_text`
- `body_text`
- `extra_text`
- `extracted_text`
- `notes_text`
- `thumb_path`
- `preview_path`
- `width`
- `height`

## Search and Retrieval

Search targets:
- Deck name
- Folder path
- Slide title
- Slide subtitle
- Slide body placeholder text
- Additional freeform text boxes and table text
- Notes text

Viewer behavior:
- Client-side filtering on exported JSON
- Search scopes are user-selectable in the UI
- Stars are stored locally in browser storage and can be filtered or prioritized in sorting

## File Opening Strategy

Direct `file:///` links are unreliable in browsers, especially when served over HTTP. The app therefore supports two modes:
- Static fallback: attempt `file:///` open when the viewer is opened directly from disk
- Preferred local mode: use the built-in `serve` command, which exposes local endpoints that open the original `.pptx` or containing folder on Windows

## Performance Notes

- Incremental scanning avoids unnecessary rerendering
- Thumbnails are lazy-loaded in the browser
- The viewer keeps search and filtering client-side for fast interaction at MVP scale
- Large archives may later require pagination or virtualization

## Risks

- PowerPoint COM can be slow or brittle on corrupted decks and is unavailable on non-Windows hosts
- Browser security rules limit local file access without the local server
- Very large archives may outgrow a single exported JSON file
- Cross-platform behavior must not accidentally make `pywin32` a required dependency on non-Windows systems
