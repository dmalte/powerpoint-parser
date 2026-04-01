"""Metadata extraction using python-pptx (pure Python, no COM)."""

from __future__ import annotations

from pptx import Presentation
from pptx.enum.shapes import PP_PLACEHOLDER
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
                    "subtitle_text": str,
                    "body_text": str,
                    "extra_text": str,
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
        subtitle_text = _get_subtitle(slide)
        body_text, extra_text = _get_text_buckets(slide)
        notes_text = _get_notes(slide)

        slides_meta.append({
            "slide_number": idx,
            "title": title,
            "subtitle_text": subtitle_text,
            "body_text": body_text,
            "extra_text": extra_text,
            "extracted_text": _combine_text_parts(title, subtitle_text, body_text, extra_text),
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


def _get_subtitle(slide) -> str:
    """Extract subtitle placeholder text when present."""
    for shape in slide.placeholders:
        if not getattr(shape, "has_text_frame", False):
            continue
        if _placeholder_type_name(shape) == "SUBTITLE":
            return _text_frame_to_text(shape.text_frame)
    return ""


def _get_text_buckets(slide) -> tuple[str, str]:
    """Return body placeholder text and additional text separately."""
    body_parts: list[str] = []
    extra_parts: list[str] = []

    for shape in slide.shapes:
        if not getattr(shape, "has_text_frame", False):
            if getattr(shape, "has_table", False):
                table_text = _get_table_text(shape)
                if table_text:
                    extra_parts.append(table_text)
            continue

        text = _text_frame_to_text(shape.text_frame)
        if not text:
            continue

        placeholder_type = _placeholder_type_name(shape)
        if placeholder_type in {"TITLE", "CENTER_TITLE", "SUBTITLE"}:
            continue
        if placeholder_type in {"BODY", "CONTENT", "OBJECT", "TEXT"}:
            body_parts.append(text)
        else:
            extra_parts.append(text)

    return "\n".join(body_parts), "\n".join(extra_parts)


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


def _placeholder_type_name(shape) -> str | None:
    if not getattr(shape, "is_placeholder", False):
        return None
    try:
        ptype = shape.placeholder_format.type
    except Exception:
        return None

    for name in dir(PP_PLACEHOLDER):
        if name.startswith("_"):
            continue
        try:
            if getattr(PP_PLACEHOLDER, name) == ptype:
                return name
        except Exception:
            continue
    return str(ptype)


def _text_frame_to_text(text_frame) -> str:
    parts: list[str] = []
    for para in text_frame.paragraphs:
        text = para.text.strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _get_table_text(shape) -> str:
    parts: list[str] = []
    try:
        for row in shape.table.rows:
            for cell in row.cells:
                text = cell.text.strip()
                if text:
                    parts.append(text)
    except Exception:
        return ""
    return "\n".join(parts)


def _combine_text_parts(*parts: str) -> str:
    ordered: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = part.strip()
        if cleaned and cleaned not in seen:
            ordered.append(cleaned)
            seen.add(cleaned)
    return "\n\n".join(ordered)
