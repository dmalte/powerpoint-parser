# PowerPoint Visual Archive — macOS distribution

This disk image contains the self-contained Apple Silicon (or stated architecture)
application, console CLI, and a self-contained per-user installation tool.

To install or upgrade, open **Install.command**. On the first install, choose an
existing local folder to index; on upgrades, the existing configuration is
preserved. The tool stages the new binaries and rolls them back if launchctl
startup fails. It runs as the signed-in user and registers a per-user LaunchAgent.
Do not upgrade while another version is actively converting files: use **Pause
Scan & Save** and verify the saved archive first. A Mac with Microsoft PowerPoint
requires Automation consent for slide rendering; PDF and Markdown work without it.

**Not notarized:** This build has an ad-hoc signature, not a Developer ID
signature or Apple notarization. macOS Gatekeeper may warn or refuse to open
it. Install only if you trust the downloaded release and its checksum; do not
disable Gatekeeper globally. The project does not claim enterprise distribution
readiness. Open **Uninstall.command** to remove binaries and its LaunchAgent;
user index, settings and logs are intentionally retained.

The CLI is included under `pptviewer/` for diagnostics and manual maintenance.
The viewer listens only on <http://127.0.0.1:8080/>. By default, Markdown
HTTPS images may be fetched when documents are indexed; enable Offline Mode in
Settings to disable these requests. Browsing previews never fetches images.
