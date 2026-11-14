"""Safe, offline HTML snippets and JPEG cards for local Markdown documents.

Markdown is parsed as CommonMark with raw HTML disabled. The generated HTML
has no executable content, remote resource loading or active links and is
displayed inside a sandboxed iframe by the viewer. Source files never change.
"""
from __future__ import annotations

import html
import re
import textwrap
from html.parser import HTMLParser
from pathlib import Path

from markdown_it import MarkdownIt
from PIL import Image, ImageDraw, ImageFont


MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_SNIPPETS = 512
TARGET_SECTION_CHARS = 3600
_CARD_SIZE = (640, 400)
_BLOCK_START = {
    "paragraph_open", "heading_open", "fence", "code_block", "blockquote_open",
    "bullet_list_open", "ordered_list_open", "table_open", "html_block", "hr",
}

_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; "
    "font-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; "
    "connect-src 'none'; script-src 'none'; form-action 'none'; base-uri 'none'"
)

_STYLE = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  color:#242936;background:#fff;margin:0;padding:28px 34px;overflow-wrap:anywhere}
main{max-width:880px;margin:auto}
h1,h2,h3,h4{color:#1e293b;line-height:1.25;margin:1.1em 0 .55em}
h1{font-size:1.65em;border-bottom:1px solid #dfe4ed;padding-bottom:.35em}
h2{font-size:1.37em}
p,ul,ol,blockquote,table,pre{margin:0 0 1.05em}
ul,ol{padding-left:1.65em}
blockquote{padding:.25em 1em;border-left:4px solid #cbd5e1;color:#465469;background:#f8fafc}
pre{background:#f2f5f9;border:1px solid #e2e8f0;border-radius:8px;padding:14px;
  overflow-x:auto;white-space:pre-wrap}
code{font:0.89em/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:#f2f5f9;
  padding:1px 4px;border-radius:3px}
pre code{padding:0;background:transparent}
table{border-collapse:collapse;width:100%;font-size:.92em}
th,td{border:1px solid #dce3ed;padding:7px 10px;text-align:left}
th{background:#f1f5f9}
hr{border:0;border-top:1px solid #dce3ed;margin:1.4em 0}
.md-image-placeholder{display:inline-block;color:#526276;background:#edf2f7;border-radius:6px;padding:4px 8px}
.md-link{color:#24639b;text-decoration:underline}
.meta{font-size:.8em;color:#64748b;text-transform:uppercase;letter-spacing:.08em}
"""

def _parser() -> MarkdownIt:
    parser = MarkdownIt("commonmark", {"html": False, "linkify": False, "breaks": True})
    parser.enable("table")

    # Make links inert so no user Markdown content becomes an active navigation
    # target. Obsidian deep links will be introduced via a trusted UI action.
    parser.add_render_rule("link_open", lambda renderer, tokens, idx, options, env: '<span class="md-link">')
    parser.add_render_rule("link_close", lambda renderer, tokens, idx, options, env: "</span>")
    parser.add_render_rule(
        "image",
        lambda renderer, tokens, idx, options, env: (
            '<span class="md-image-placeholder">Image: '
            + html.escape(tokens[idx].content, quote=True) + "</span>"
        ),
    )
    return parser


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, text: str) -> None:
        self.parts.append(text)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def _text_from_html(fragment: str) -> str:
    parser = _TextExtractor()
    parser.feed(fragment)
    return parser.text()


def _remove_yaml_frontmatter(source: str) -> str:
    lines = source.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return source
    for index in range(1, min(len(lines), 150)):
        if lines[index].strip() in {"---", "..."}:
            return "".join(lines[index + 1:])
    return source


def _section_starts(parser: MarkdownIt, lines: list[str]) -> list[tuple[int, str]]:
    joined = "".join(lines)
    headings: list[tuple[int, str]] = []
    tokens = parser.parse(joined)
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or not token.map or token.tag not in {"h1", "h2", "h3", "h4"}:
            continue
        inline = tokens[index + 1] if index + 1 < len(tokens) else None
        heading = _text_from_html(parser.render(inline.content)) if inline else ""
        headings.append((token.map[0], heading or "Untitled section"))
    return headings


def _chunk_section(parser: MarkdownIt, content: str, max_chars: int) -> list[str]:
    if len(content) <= max_chars:
        return [content]
    lines = content.splitlines(keepends=True)
    cuts = {0, len(lines)}
    for token in parser.parse(content):
        if token.level == 0 and token.map and token.type in _BLOCK_START:
            cuts.add(token.map[0])
    boundaries = sorted(cuts)
    blocks = ["".join(lines[a:b]) for a, b in zip(boundaries, boundaries[1:]) if a < b]
    groups: list[str] = []
    current = ""
    for block in blocks:
        if current and len(current) + len(block) > max_chars:
            groups.append(current)
            current = ""
        current += block
    if current.strip():
        groups.append(current)
    return groups or [content]


def split_markdown(source: str, file_stem: str) -> list[tuple[str, str]]:
    """Return section titles and Markdown content, preserving source ordering.

    Headings within fenced code do not split a document. A long section can
    produce multiple snippets, but a code fence/table is never cut in half.
    """
    parser = _parser()
    without_frontmatter = _remove_yaml_frontmatter(source)
    lines = without_frontmatter.splitlines(keepends=True)
    if not lines or not without_frontmatter.strip():
        return [((file_stem or "Untitled note"), "")]
    starts = _section_starts(parser, lines)
    sections: list[tuple[str, str]] = []
    if not starts:
        sections.append((file_stem or "Untitled note", without_frontmatter))
    else:
        if starts[0][0] > 0 and "".join(lines[:starts[0][0]]).strip():
            sections.append((file_stem or "Introduction", "".join(lines[:starts[0][0]])))
        for index, (first, title) in enumerate(starts):
            last = starts[index + 1][0] if index + 1 < len(starts) else len(lines)
            sections.append((title, "".join(lines[first:last])))
    result: list[tuple[str, str]] = []
    for title, segment in sections:
        for i, block in enumerate(_chunk_section(parser, segment, TARGET_SECTION_CHARS)):
            result.append((title if i == 0 else title + f" (part {i + 1})", block))
            if len(result) > MAX_SNIPPETS:
                raise ValueError("Markdown file contains too many snippet sections")
    return result or [(file_stem or "Untitled note", "")]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        ["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Helvetica-Bold.ttf"]
        if bold else
        ["DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttf"]
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _thumbnail(path: Path, title: str, excerpt: str, number: int) -> None:
    image = Image.new("RGB", _CARD_SIZE, (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((18, 18, 622, 382), radius=16, fill=(249, 250, 253), outline=(218, 226, 239), width=2)
    draw.rounded_rectangle((38, 37, 165, 69), radius=12, fill=(229, 239, 250))
    draw.text((53, 41), "MARKDOWN", fill=(37, 87, 135), font=_font(16, True))
    draw.text((536, 42), f"#{number}", fill=(110, 123, 140), font=_font(17))
    y = 90
    title_font = _font(31, True)
    for line in textwrap.wrap(title or "Untitled note", width=33, break_long_words=True)[:3]:
        draw.text((42, y), line, fill=(35, 48, 69), font=title_font)
        y += 39
    y = max(y + 10, 190)
    draw.line((42, y, 596, y), fill=(215, 223, 235), width=2)
    y += 20
    body_font = _font(20)
    for line in textwrap.wrap(excerpt or "Empty section", width=57, break_long_words=True)[:6]:
        if y + 26 > 355:
            break
        draw.text((43, y), line, fill=(86, 98, 118), font=body_font)
        y += 27
    image.save(path, format="JPEG", quality=86, optimize=True)


def render_markdown_snippets(source: str | Path, output_dir: str | Path) -> list[dict]:
    """Render each Markdown section to a JPEG card and restricted local HTML."""
    source = Path(source)
    if source.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Markdown file exceeds the configured safety limit")
    text = source.read_text(encoding="utf-8-sig")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    parser = _parser()
    result = []
    for number, (title, markdown_section) in enumerate(split_markdown(text, source.stem), 1):
        body_html = parser.render(markdown_section)
        text_value = _text_from_html(body_html)
        preview_name = f"preview_{number:03d}.html"
        thumb_name = f"thumb_{number:03d}.jpg"
        page = (
            "<!DOCTYPE html><html lang=\"en\"><head>"
            "<meta charset=\"UTF-8\">"
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="' + html.escape(_CSP, quote=True) + '">'
            "<title>" + html.escape(title, quote=True) + "</title>"
            "<style>" + _STYLE + "</style></head><body><main>"
            '<div class="meta">Markdown section ' + str(number) + "</div>"
            + body_html + "</main></body></html>"
        )
        (out / preview_name).write_text(page, encoding="utf-8")
        _thumbnail(out / thumb_name, title, text_value, number)
        result.append({
            "slide_number": number,
            "title": title,
            "body_text": text_value,
            "extracted_text": text_value,
            "thumb_path": thumb_name,
            "preview_path": preview_name,
            "width": _CARD_SIZE[0],
            "height": _CARD_SIZE[1],
        })
    return result
