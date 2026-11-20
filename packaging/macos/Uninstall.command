#!/bin/zsh
# Remove application binaries and LaunchAgent, preserving user documents/index.
set -euo pipefail
bundle_dir="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -x "$bundle_dir/pptviewer-installer" ]]; then
  echo "Missing bundled installer." >&2
  exit 2
fi
"$bundle_dir/pptviewer-installer" --uninstall
echo 'Your archive, configuration and logs remain in Application Support.'
