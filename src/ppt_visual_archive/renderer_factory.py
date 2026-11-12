"""Select a PowerPoint slide image renderer without changing shared indexing.

Windows always uses the established COM renderer. macOS defaults to native
PowerPoint/AppleScript; LibreOffice must be explicitly selected in config.
"""
from __future__ import annotations

import sys
from typing import Protocol

from .config import RenderConfig


class SlideRenderer(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def export_slides(self, pptx_path: str, output_dir: str) -> list[dict]: ...


def create_pptx_renderer(
    config: RenderConfig, *, platform_name: str | None = None
) -> SlideRenderer:
    platform = sys.platform if platform_name is None else platform_name
    if platform == "win32":
        from .renderer import PowerPointRenderer
        return PowerPointRenderer(config)

    backend = config.mac_pptx_backend.strip().lower()
    if backend not in {"powerpoint", "libreoffice"}:
        raise ValueError("Unsupported mac_pptx_backend; use powerpoint or libreoffice")

    if backend == "libreoffice":
        from .mac_renderer import LibreOfficeRenderer
        return LibreOfficeRenderer(config)

    if platform == "darwin":
        from .mac_renderer import MacPowerPointRenderer
        return MacPowerPointRenderer(config)

    raise RuntimeError(
        "PPTX rendering requires PowerPoint COM on Windows or PowerPoint for Mac. "
        "On Linux, explicitly select mac_pptx_backend: libreoffice, or index PDF only."
    )
