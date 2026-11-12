# macOS Architecture and Implementation Plan

- Feature: specs/004-macos-desktop-agent
- Milestone: M008
- Requirements: REQ-MAC-001

## Data Flow

- Windows PPTX → current COM Renderer.export_slides → images; python-pptx → text/notes; shared SQLite/JSON.
- Mac PPTX → PowerPoint AppleScript saved PDF → PyMuPDF → the same final images; python-pptx → original text/notes; shared SQLite/JSON.
- Optional Mac fallback: user explicitly configures LibreOffice headless PDF conversion, same rasterizer.
- Original PDFs use existing PyMuPDF handler unchanged.

## Implementation

- New renderer implements start/stop/export_slides. Factory selects COM on Windows, PowerPoint/AppleScript on Mac, optional LibreOffice on non-Windows.
- osascript uses argv for untrusted paths, never script string interpolation; timeout and validated page count, subprocess logs paths only locally. Automate only a temporary copy of the PPTX to avoid closing a user's open original. Do not quit user's PowerPoint process or return raw stderr through HTTP status.
- Rasterize in private temporary output; promote successful JPEGs into deck assets. No intermediate PDF persists.
- Persist macOS file paths under Application Support, and use macOS open/open -R for Finder actions.
- Build optional per-user LaunchAgent and PyInstaller Mac packaging scaffold. No new production Python dependencies. Tests mock osascript and LibreOffice; no false claims about real Mac compilation.
- Renderer image files remain nontransactional with SQLite/JSON; image versioning is separate.

## Limits

- PowerPoint GUI supports JPEG export, but unattended AppleScript JPEG export not proven; temp PDF is pragmatic first automation backend.
- Mac-only PowerPoint AppleScript, Automation consent, native package build, login launch, and fidelity need validation on a real Mac. No macOS launch privileges assumed on Pi.
