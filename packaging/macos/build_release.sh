#!/usr/bin/env bash
# Create a native macOS distribution image without changing any installed app.
# Usage: packaging/macos/build_release.sh <40-hex-committed-source-SHA>
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "A macOS build host is required for release imaging." >&2
  exit 2
fi
if [[ "${1:-}" =~ ^[[:xdigit:]]{40}$ ]]; then
  source_revision="$1"
else
  echo "Supply the verified 40-character source commit SHA." >&2
  exit 2
fi
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
if [[ ! -x .venv/bin/python || ! -f dist/PowerPointArchiveAgent.app/Contents/MacOS/PowerPointArchiveAgent || ! -x dist/pptviewer/pptviewer ]]; then
  echo "Build dist/PowerPointArchiveAgent.app and dist/pptviewer first with packaging/macos/build.sh." >&2
  exit 2
fi
version="$(.venv/bin/python -c 'from pathlib import Path;import re;s=Path("pyproject.toml").read_text();m=re.search(r"^version\s*=\s*\"([0-9]+\.[0-9]+\.[0-9]+)\"",s,re.M);assert m;print(m.group(1))')"
arch="$(uname -m)"

# Compile the already-tested stdlib lifecycle/rollback installer into a
# self-contained console binary. No separate Python is needed to install.
.venv/bin/python -m PyInstaller --clean --noconfirm --onefile --console \
  --name pptviewer-installer packaging/macos/install_agent.py

stage="$(mktemp -d "${TMPDIR:-/tmp}/pptviewer-release.XXXXXXXX")"
trap 'rm -rf "$stage"' EXIT
cp -R dist/PowerPointArchiveAgent.app "$stage/PowerPointArchiveAgent.app"
cp -R dist/pptviewer "$stage/pptviewer"
cp dist/pptviewer-installer "$stage/pptviewer-installer"
cp packaging/macos/Install.command "$stage/Install.command"
cp packaging/macos/Uninstall.command "$stage/Uninstall.command"
cp packaging/macos/RELEASE_INSTALL.md "$stage/README.md"
chmod 755 "$stage/Install.command" "$stage/Uninstall.command" "$stage/pptviewer-installer"
printf 'Version: %s\nSource revision: %s\nPlatform: macOS %s\nSigning: ad-hoc; not Developer ID signed or notarized\n' \
  "$version" "$source_revision" "$arch" > "$stage/BUILD_INFO.txt"

# Verify the shipped installer can inspect the exact staged bundles.
"$stage/pptviewer-installer" --plan --artifacts "$stage" > "$stage/installer-plan.json"
.venv/bin/python -c 'import json,sys;d=json.load(open(sys.argv[1]));assert d["app_artifact_available"] and d["cli_artifact_available"]' "$stage/installer-plan.json"
rm "$stage/installer-plan.json"  # machine-local install paths must not ship
mkdir -p dist/release
image="dist/release/PowerPointVisualArchive-macOS-${arch}-${version}-unnotarized.dmg"
hdiutil create -quiet -ov -format UDZO -volname "PowerPoint Visual Archive ${version}" \
  -srcfolder "$stage" "$image"
hdiutil verify -quiet "$image"
codesign --verify --deep --strict "$stage/PowerPointArchiveAgent.app"
shasum -a 256 "$image"
echo "Created $image (unsigned/not notarized, no installed agents modified)"
