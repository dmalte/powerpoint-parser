"""PDF page extraction and rendering using PyMuPDF (fitz)."""

from __future__ import annotations

import os
from pathlib import Path

from .config import RenderConfig
from .utils import ensure_dir, logger


def extract_and_render_pdf(
    pdf_path: str, output_dir: str, render_config: RenderConfig
) -> dict:
    """Extract text and render page images from a PDF file.

    Returns the same structure as extractor.extract_metadata() merged with
    renderer results so the pipeline can treat it uniformly:
        {
            "slide_count": int,
            "width": int,
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
                    "thumb_path": str,   # relative filename
                    "preview_path": str,
                    "thumb_width": int,
                    "thumb_height": int,
                },
                ...
            ]
        }
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required for PDF support. Install it with: pip install PyMuPDF"
        ) from exc

    ensure_dir(output_dir)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.error("Cannot open PDF %s: %s", pdf_path, e)
        return {"slide_count": 0, "width": 0, "height": 0, "slides": []}

    # Password-protected PDFs must report an explicit fixed failure reason.
    # Otherwise their page-access exception varies by PyMuPDF version, making
    # a permanent encrypted source look like a retryable corrupt PDF.
    if doc.needs_pass:
        doc.close()
        raise ValueError("PDF is encrypted and requires a password")

    slides_out: list[dict] = []
    page_count = doc.page_count
    width_px = 0
    height_px = 0

    for page_num in range(page_count):
        page = doc[page_num]
        snum = page_num + 1

        # Page dimensions (points → pixels at 96 DPI)
        rect = page.rect
        pw = int(rect.width * 96 / 72)
        ph = int(rect.height * 96 / 72)
        if snum == 1:
            width_px = pw
            height_px = ph

        # ── Extract text ──
        page_text = page.get_text("text").strip()
        # Use the first line as a pseudo-title
        lines = page_text.split("\n") if page_text else []
        title = lines[0].strip() if lines else ""
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        # ── Render thumbnail ──
        thumb_name = f"thumb_{snum:03d}.{render_config.image_format}"
        thumb_path = os.path.join(output_dir, thumb_name)
        thumb_w = render_config.thumbnail_width
        thumb_scale = thumb_w / rect.width if rect.width else 1.0
        thumb_h = int(rect.height * thumb_scale)
        try:
            mat = fitz.Matrix(thumb_scale, thumb_scale)
            pix = page.get_pixmap(matrix=mat)
            pix.save(thumb_path)
        except Exception as e:
            logger.warning("Failed to render PDF thumbnail page %d: %s", snum, e)
            thumb_name = ""

        # ── Render preview ──
        prev_name = f"preview_{snum:03d}.{render_config.image_format}"
        prev_path = os.path.join(output_dir, prev_name)
        prev_w = render_config.preview_width
        prev_scale = prev_w / rect.width if rect.width else 1.0
        try:
            mat = fitz.Matrix(prev_scale, prev_scale)
            pix = page.get_pixmap(matrix=mat)
            pix.save(prev_path)
        except Exception as e:
            logger.warning("Failed to render PDF preview page %d: %s", snum, e)
            prev_name = ""

        slides_out.append({
            "slide_number": snum,
            "title": title,
            "subtitle_text": "",
            "body_text": body,
            "extra_text": "",
            "extracted_text": page_text,
            "notes_text": "",
            "thumb_path": thumb_name,
            "preview_path": prev_name,
            "thumb_width": thumb_w,
            "thumb_height": thumb_h,
        })

    doc.close()

    logger.debug("Processed PDF %s: %d pages", pdf_path, page_count)
    return {
        "slide_count": page_count,
        "width": width_px,
        "height": height_px,
        "slides": slides_out,
    }
