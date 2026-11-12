"""macOS PowerPoint rendering with Windows-compatible final image artifacts.

Microsoft PowerPoint for Mac has a documented AppleScript PDF save command. The
JPEG Export GUI is not treated as a scriptable API until verified on an actual
Mac. PDF is strictly transient: no PDF enters SQLite or the generated viewer.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import RenderConfig
from .pdf_processor import extract_and_render_pdf
from .utils import logger

# Pass user paths via the osascript argv handler. Never interpolate paths into
# AppleScript source or invoke a shell. Compile/execute on macOS before release.
POWERPOINT_PDF_APPLESCRIPT = """
on run argv
    set inputPath to item 1 of argv
    set outputPath to item 2 of argv
    set sourceFile to POSIX file inputPath as alias
    set resultFile to POSIX file outputPath
    tell application "Microsoft PowerPoint"
        open sourceFile
        set importedPresentation to active presentation
        try
            save importedPresentation in resultFile as save as PDF
        on error errText number errCode
            close importedPresentation saving no
            error errText number errCode
        end try
        close importedPresentation saving no
    end tell
end run
""".strip()


class _MacPdfBackedRenderer:
    """Adapter conforming to start/stop/export_slides used by the shared pipeline."""

    def __init__(self, config: RenderConfig) -> None:
        self.config = config
        self._executable: str | None = None

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        # Do not quit Microsoft PowerPoint: user may have other presentations open.
        return None

    def _convert(self, source: Path, pdf_path: Path, workdir: Path) -> None:
        raise NotImplementedError

    def export_slides(self, pptx_path: str, output_dir: str) -> list[dict]:
        """Convert PPTX to ephemeral PDF, render, then publish JPEG/PNG images.

        Uses a temp directory on the same output filesystem, so os.replace can
        promote each complete image without partial writes or cross-device moves.
        """
        if self._executable is None:
            self.start()
        source = Path(pptx_path).resolve(strict=True)
        if not source.is_file():
            raise FileNotFoundError(source)
        dest = Path(output_dir).resolve()
        dest.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".pptviewer-mac-", dir=dest.parent) as tmp_name:
            workdir = Path(tmp_name)
            # PowerPoint may already have the original open with unsaved edits.
            # Open only a private copy, so closing our automation document can
            # never close or save an existing user presentation.
            local_source = workdir / source.name
            shutil.copy2(source, local_source)
            pdf_path = workdir / "presentation.pdf"
            self._convert(local_source, pdf_path, workdir)
            if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
                raise RuntimeError("PowerPoint conversion produced no PDF")
            raster_dir = workdir / "images"
            data = extract_and_render_pdf(str(pdf_path), str(raster_dir), self.config)
            pages = data.get("slides") or []
            if data.get("slide_count", 0) <= 0 or len(pages) != data["slide_count"]:
                raise RuntimeError("Converted PowerPoint PDF has missing or unreadable pages")
            results = []
            for page in pages:
                thumb = page.get("thumb_path")
                preview = page.get("preview_path")
                if not thumb or not preview or not (raster_dir / thumb).is_file() or not (raster_dir / preview).is_file():
                    raise RuntimeError("Converted PowerPoint slide image is missing")
                results.append({
                    "slide_number": page["slide_number"],
                    "thumb_path": thumb,
                    "preview_path": preview,
                    "width": page["thumb_width"],
                    "height": page["thumb_height"],
                })
            # No final images are touched until every page rendered successfully.
            for result in results:
                for key in ("thumb_path", "preview_path"):
                    filename = result[key]
                    os.replace(raster_dir / filename, dest / filename)
            logger.info("Rendered %d PowerPoint slides via temporary PDF", len(results))
            return results


class MacPowerPointRenderer(_MacPdfBackedRenderer):
    """PowerPoint for Mac + AppleScript save-as-PDF bridge (macOS acceptance pending)."""

    def start(self) -> None:
        self._executable = shutil.which("osascript")
        if not self._executable:
            raise RuntimeError(
                "Mac PowerPoint rendering requires macOS osascript and Microsoft PowerPoint. "
                "Select mac_pptx_backend: libreoffice only if you explicitly accept its fidelity tradeoff."
            )

    def _convert(self, source: Path, pdf_path: Path, workdir: Path) -> None:
        assert self._executable
        try:
            subprocess.run(
                [self._executable, "-e", POWERPOINT_PDF_APPLESCRIPT, str(source), str(pdf_path)],
                check=True, capture_output=True, text=True,
                timeout=self.config.pptx_conversion_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("PowerPoint for Mac PDF conversion timed out") from exc
        except subprocess.CalledProcessError as exc:
            # Preserve actionable OS error but do not leak an uncontrolled console dump.
            logger.warning(
                "PowerPoint for Mac PDF conversion command failed (exit %s): %s",
                exc.returncode, (exc.stderr or "").strip()[:500],
            )
            # Keep filenames and local source paths out of /api/status errors.
            raise RuntimeError(
                "PowerPoint for Mac AppleScript PDF export failed. Check PowerPoint "
                "installation, macOS Automation permission, and local file access."
            ) from exc


class LibreOfficeRenderer(_MacPdfBackedRenderer):
    """Explicit LibreOffice conversion; not an automatic fidelity fallback."""

    def start(self) -> None:
        self._executable = shutil.which("soffice") or shutil.which("libreoffice")
        if not self._executable:
            # A normal macOS app installation may not put soffice on PATH.
            candidates = [
                Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
                Path.home() / "Applications/LibreOffice.app/Contents/MacOS/soffice",
            ]
            self._executable = next((str(p) for p in candidates if p.is_file()), None)
        if not self._executable:
            raise RuntimeError("LibreOffice renderer selected but soffice was not found")

    def _convert(self, source: Path, pdf_path: Path, workdir: Path) -> None:
        assert self._executable
        profile = workdir / "lo-profile"
        pdf_dir = workdir / "pdf-out"
        pdf_dir.mkdir()
        cmd = [
            self._executable, f"-env:UserInstallation={profile.as_uri()}",
            "--headless", "--convert-to", "pdf:impress_pdf_Export",
            "--outdir", str(pdf_dir), str(source),
        ]
        try:
            subprocess.run(
                cmd, check=True, capture_output=True, text=True,
                timeout=self.config.pptx_conversion_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("LibreOffice PowerPoint conversion timed out") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("LibreOffice PowerPoint PDF conversion failed") from exc
        exported = pdf_dir / (source.stem + ".pdf")
        if not exported.is_file():
            raise RuntimeError("LibreOffice conversion produced no PDF")
        os.replace(exported, pdf_path)
