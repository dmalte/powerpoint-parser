# PowerPoint Visual Archive Viewer

An offline-first visual index for PowerPoint presentations, PDFs and Markdown notes. Browse slide thumbnails, search extracted text, and open an original document from a local HTML viewer. The archive and source documents stay on your computer.

## Platform support

- **Windows:** PowerPoint slide rendering uses Microsoft PowerPoint COM in the signed-in user's session. The per-user installer source is under `packaging/windows/`. Windows installer/COM acceptance is still in progress.
- **macOS:** PowerPoint-to-temporary-PDF automation with local JPEG thumbnails, a user-session agent and per-user installer source under `packaging/macos/`. Automated Office access may require macOS consent; app notarization and cross-platform visual parity are not yet certified.
- **Linux or macOS without PowerPoint:** PDF and Markdown indexing work without Microsoft Office. PowerPoint rendering requires a configured supported backend.

Requires Python 3.10 or later. This source distribution includes the necessary frontend, dependency metadata, build definitions and tests; it does **not** ship signed installers.

## Install from source

```bash
python -m venv .venv
# Activate the environment for your shell, then:
python -m pip install -e .
python -c "from pathlib import Path; import shutil; shutil.copy2('config/config.example.yaml', 'config.yaml')"
```

Edit `config.yaml` for your scan roots, enabled formats (`pptx`, `pdf`, `md`), and output directory. Real machine configuration is ignored by Git.

```bash
pptviewer scan --config config.yaml
pptviewer build --config config.yaml
pptviewer serve --config config.yaml --port 8080
```

Open `http://127.0.0.1:8080/`. To use the per-user background agent and local Settings controls instead, run `pptviewer agent --config config.yaml` (or an installed native app). The local web server binds to loopback; do not expose it to the internet.

## Viewer and conversion features

- Incremental source indexing with safe per-document SQLite updates and immutable preview generations. A PDF/PowerPoint failure does not replace an existing good index entry.
- A searchable, paginated thumbnail grid (at most 240 cards at once), document list (at most 100 rows), directory includes/excludes, presentation/date/type filters, starred slides, and text-scope search.
- One US Letter first-page JPEG preview and thumbnail per Markdown document, including safe locally referenced images. Text beyond the first preview page remains searchable; source files are unchanged.
- Native agent **Pause Scan & Save** and **Resume Scan** controls, including saved partial archives and a persisted pause preference.
- A private local retry ledger: unchanged encrypted PDFs are held until changed or manually reset; transient PowerPoint/permission failures use increasing 5-minute, 30-minute, 2-hour, then 6-hour retry windows. **Retry Deferred Files** is available from Settings. The ledger holds only hashed file identities and fixed status metadata outside the served archive.
- Local path-free diagnostics, conversion failure classification and optional performance reports. Historical images are intentionally retained until an explicit cleanup policy is chosen.

## Development and native packaging

```bash
python -m pip install -e ".[dev]"
python -m pytest tests -q
```

The public source includes the preflight/build tools referenced by `packaging/windows/README.md` and `packaging/macos/README.md`. Before distributing a native installer, complete testing on the target OS, including actual PowerPoint automation, file permissions, installer upgrades and code signing. Successful source checks are not equivalent to a signed release.

## Privacy and publication

This repository is a curated public source distribution. Internal development notes, machine-specific configuration, agent instructions, local logs, databases and credentials are excluded. It is not a place to submit private user documents or access tokens. GitHub publication history predating this curated distribution may still contain older project files.

## License

MIT — see [LICENSE](LICENSE).
