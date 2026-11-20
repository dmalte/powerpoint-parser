#!/bin/zsh
# Per-user install/upgrade from a verified native release image.
set -euo pipefail
bundle_dir="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -x "$bundle_dir/pptviewer-installer" ]]; then
  echo "Missing bundled installer. Reopen the official release image." >&2
  exit 2
fi
scan_root="$HOME/Documents"
config="$HOME/Library/Application Support/PowerPointVisualArchive/config.yaml"
if [[ ! -f "$config" ]]; then
  printf 'Folder to index on first installation [%s]: ' "$scan_root"
  read -r typed_root
  if [[ -n "$typed_root" ]]; then scan_root="$typed_root"; fi
  if [[ ! -d "$scan_root" ]]; then
    echo "Folder not found; no installation was started." >&2
    exit 2
  fi
fi
"$bundle_dir/pptviewer-installer" --install --artifacts "$bundle_dir" --root "$scan_root"
echo "Installed for the current user. View the archive at http://127.0.0.1:8080/"
echo 'You may close this window.'
