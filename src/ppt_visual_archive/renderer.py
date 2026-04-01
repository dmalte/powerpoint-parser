"""PowerPoint COM automation renderer (Windows only).

Exports slide images via the installed PowerPoint application.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from .config import RenderConfig
from .utils import ensure_dir, logger


class PowerPointRenderer:
    """Renders slide images using PowerPoint COM automation."""

    def __init__(self, render_config: RenderConfig) -> None:
        self.config = render_config
        self._app = None

    def start(self) -> None:
        """Launch PowerPoint application."""
        try:
            import win32com.client
            import pythoncom

            pythoncom.CoInitialize()
            self._app = win32com.client.Dispatch("PowerPoint.Application")
            # Keep PowerPoint visible=False in background; some versions
            # require Visible=True or the export may fail silently.
            # We use a msoFalse constant (0). Switch to 1 if issues arise.
            logger.info("PowerPoint COM application started")
        except Exception as e:
            logger.error("Failed to start PowerPoint COM: %s", e)
            raise RuntimeError(
                "Could not start PowerPoint. Ensure Microsoft PowerPoint is installed."
            ) from e

    def stop(self) -> None:
        """Quit PowerPoint application."""
        if self._app is not None:
            try:
                self._app.Quit()
            except Exception:
                pass
            self._app = None
            logger.info("PowerPoint COM application stopped")

    def export_slides(
        self, pptx_path: str, output_dir: str
    ) -> list[dict]:
        """Export all slides from a presentation as images.

        Returns list of dicts: [{slide_number, thumb_path, preview_path, width, height}, ...]
        """
        if self._app is None:
            self.start()

        pptx_path = str(Path(pptx_path).resolve())
        ensure_dir(output_dir)
        results = []

        pres = None
        try:
            pres = self._app.Presentations.Open(
                pptx_path,
                ReadOnly=True,   # msoTrue
                Untitled=False,  # msoFalse
                WithWindow=False,  # msoFalse — no UI window
            )

            slide_width = pres.PageSetup.SlideWidth   # points
            slide_height = pres.PageSetup.SlideHeight  # points
            aspect = slide_height / slide_width if slide_width > 0 else 0.5625

            for i, slide in enumerate(pres.Slides, start=1):
                slide_num = i
                slide_info = {"slide_number": slide_num}

                # ── Thumbnail ──
                thumb_w = self.config.thumbnail_width
                thumb_h = int(thumb_w * aspect)
                thumb_name = f"thumb_{slide_num:03d}.{self.config.image_format}"
                thumb_full = os.path.join(output_dir, thumb_name)

                try:
                    slide.Export(thumb_full, self.config.image_format.upper(), thumb_w, thumb_h)
                    slide_info["thumb_path"] = thumb_name
                except Exception as e:
                    logger.warning("Failed to export thumbnail slide %d: %s", slide_num, e)
                    slide_info["thumb_path"] = ""

                # ── Preview ──
                prev_w = self.config.preview_width
                prev_h = int(prev_w * aspect)
                prev_name = f"preview_{slide_num:03d}.{self.config.image_format}"
                prev_full = os.path.join(output_dir, prev_name)

                try:
                    slide.Export(prev_full, self.config.image_format.upper(), prev_w, prev_h)
                    slide_info["preview_path"] = prev_name
                except Exception as e:
                    logger.warning("Failed to export preview slide %d: %s", slide_num, e)
                    slide_info["preview_path"] = ""

                slide_info["width"] = thumb_w
                slide_info["height"] = thumb_h
                results.append(slide_info)

            logger.debug("Exported %d slides from %s", len(results), pptx_path)

        except Exception as e:
            logger.error("Error processing %s: %s", pptx_path, e)
            raise
        finally:
            if pres is not None:
                try:
                    pres.Close()
                except Exception:
                    pass

        return results

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
