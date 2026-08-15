# LLM Guide: Refreshing the Public Staging Repository

Maintain two views of `powerpoint-parser`:

- **Private/canonical repository:** full development state, agent/workflow files, specs, roadmap, handoff material, local configuration, and publication tooling.
- **Public staging repository:** only the reusable PowerPoint/PDF archive viewer, public configuration example, functional tests, package metadata, changelog, and MIT license.

The public repository is generated from the private repository. Do not make the canonical working tree publication-safe by deleting private development material.

Before a refresh, review the current public-facing code in `src/ppt_visual_archive/`, `web/`, `config/config.example.yaml`, `pyproject.toml`, and `tests/test_core.py`. Update `publishing/templates/public-README.md` when public behavior or setup changes.

The manifest is deliberately whitelist-based. New files remain private unless they are intentionally added to `publishing/public_bundle_manifest.json`. Keep `AGENTS.md`, `PROJECT_WORKFLOW.json`, `ROADMAP.md`, `dev/`, `spec/`, `specs/`, workflow tooling, local `config.yaml`, generated viewer output, virtual environments, caches, credentials, and machine-specific paths out of the public bundle.

Refresh with:

```bash
python tools/export_public_bundle.py ../_export/powerpoint-parser --force
```

Treat any high-severity scan finding as a publication blocker. Inspect the generated tree and public Git diff, then run tests from the staging checkout. Commit and push only from the staging checkout; the exporter itself must never publish.
