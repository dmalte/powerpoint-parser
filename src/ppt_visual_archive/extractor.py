"""Metadata extraction using python-pptx (pure Python, no COM)."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

from .utils import logger


def extract_metadata(pptx_path: str) -> dict:
    """Extract deck-level and per-slide metadata from a .pptx file.

    Returns:
        {
            "slide_count": int,
            "width": int,   # pixels (approx from EMU)
            "height": int,
            "slides": [
                {
                    "slide_number": int,
                    "title": str,
                    "extracted_text": str,
                    "notes_text": str,
                },
                ...
            ]
        }
    """
    try:
        prs = Presentation(pptx_path)
    except Exception as e:
        logger.error("Cannot open %s with python-pptx: %s", pptx_path, e)
        return {"slide_count": 0, "width": 0, "height": 0, "slides": []}

    # Deck dimensions (EMU → pixels at 96 DPI)
    width_px = int(prs.slide_width / Emu(1)) * 96 // 914400 if prs.slide_width else 0
    height_px = int(prs.slide_height / Emu(1)) * 96 // 914400 if prs.slide_height else 0

    slides_meta: list[dict] = []
    for idx, slide in enumerate(prs.slides, start=1):
        title = _get_title(slide)
        body_text = _get_body_text(slide)
        notes_text = _get_notes(slide)

        slides_meta.append({
            "slide_number": idx,
            "title": title,
            "extracted_text": body_text,
            "notes_text": notes_text,
        })

    return {
        "slide_count": len(slides_meta),
        "width": width_px,
        "height": height_px,
        "slides": slides_meta,
    }


def _get_title(slide) -> str:
    """Extract the slide title if a title placeholder exists."""
    if slide.shapes.title and slide.shapes.title.has_text_frame:
        return slide.shapes.title.text_frame.text.strip()
    # Fallback: look for the first placeholder that is a title type
    for shape in slide.placeholders:
        if shape.placeholder_format.idx == 0 and shape.has_text_frame:
            return shape.text_frame.text.strip()
    return ""


def _get_body_text(slide) -> str:
    """Concatenate all text from all shapes on the slide."""
    parts: list[str] = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                text = para.text.strip()
                if text:
                    parts.append(text)
    return "\n".join(parts)


def _get_notes(slide) -> str:
    """Extract slide notes text."""
    try:
        if slide.has_notes_slide:
            notes_slide = slide.notes_slide
            if notes_slide.notes_text_frame:
                return notes_slide.notes_text_frame.text.strip()
    except Exception:
        pass
    return ""
