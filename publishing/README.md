# Public bundle refresh

This directory contains private publication tooling for `powerpoint-parser` and is not copied into the public bundle.

The canonical repository remains the private development view. The public GitHub view is generated into the workspace staging area:

```bash
python tools/export_public_bundle.py ../_export/powerpoint-parser --force
```

The exporter uses an explicit whitelist, replaces the root README with `publishing/templates/public-README.md`, preserves an existing target `.git` directory, and scans generated text files for high-severity private-data patterns.

The public bundle includes the runtime package, web assets, example configuration, core functional tests, package metadata, changelog, `.gitignore`, and MIT license. It intentionally excludes `AGENTS.md`, `PROJECT_WORKFLOW.json`, `ROADMAP.md`, `dev/`, `spec/`, `specs/`, workflow scripts/tests, local configuration, virtual environments, and generated archive output.

Review the generated tree, run its tests, and inspect its Git diff before committing or pushing from the staging checkout. Publication is deliberately separate from bundle generation.
