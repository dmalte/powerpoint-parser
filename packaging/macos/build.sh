#!/usr/bin/env bash
# Build a per-user Mac app and console CLI on a native macOS build host.
# Does not install, launch or change any user settings.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "A macOS machine is required to run PyInstaller for a Mac bundle." >&2
  exit 2
fi

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo_root"

python_bin="python3"
if [[ ! -x ".venv/bin/python" ]]; then
  "$python_bin" -m venv .venv
fi
.venv/bin/python scripts/preflight_macos_package.py
.venv/bin/python -m pip install -e ".[dev,packaging]"
.venv/bin/python -m PyInstaller --clean --noconfirm packaging/macos/PowerPointVisualArchive.spec
.venv/bin/python scripts/preflight_macos_package.py --artifacts dist

echo "Prepared dist/PowerPointArchiveAgent.app and dist/pptviewer/"
echo "Signing/notarization and real PowerPoint automation remain to be tested on macOS."
