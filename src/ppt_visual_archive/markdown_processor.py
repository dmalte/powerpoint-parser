"""Safe, offline HTML snippets and JPEG cards for local Markdown documents.

Markdown is parsed as CommonMark with raw HTML disabled. The generated HTML
has no executable content, remote resource loading or active links and is
displayed inside a sandboxed iframe by the viewer. Source files never change.
"""
from __future__ import annotations

import html
import re
import textwrap
import warnings
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from markdown_it import MarkdownIt
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError


MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_SNIPPETS = 512
TARGET_SECTION_CHARS = 3600
_CARD_SIZE = (640, 400)
MAX_LOCAL_IMAGES = 48
MAX_LOCAL_IMAGE_BYTES = 12 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 64 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
_SAFE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_SAFE_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
_BLOCK_START = {
    "paragraph_open", "heading_open", "fence", "code_block", "blockquote_open",
    "bullet_list_open", "ordered_list_open", "table_open", "html_block", "hr",
}

_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
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
.md-local-image{display:block;max-width:100%;height:auto;margin:12px auto;border-radius:6px}
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
    def render_image(renderer, tokens, idx, options, env):
        token = tokens[idx]
        alt = html.escape(token.content or "Referenced image", quote=True)
        image_resolver = env.get("local_image_resolver")
        filename = image_resolver(token.attrGet("src") or "") if image_resolver else None
        if filename:
            # Filename is a controlled generated basename, never raw Markdown.
            return '<img class="md-local-image" loading="lazy" src="' + html.escape(filename, quote=True) + '" alt="' + alt + '">'
        return '<span class="md-image-placeholder">Image: ' + alt + "</span>"

    parser.add_render_rule("image", render_image)
    return parser


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, text: str) -> None:
        self.parts.append(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            alt = dict(attrs).get("alt") or ""
            self.parts.append(alt)

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


def _thumbnail(
    path: Path, title: str, excerpt: str, number: int,
    first_image: Path | None = None,
) -> None:
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
    if first_image is not None and first_image.is_file():
        with Image.open(first_image) as picture:
            picture = picture.convert("RGB")
            picture.thumbnail((238, 148), Image.Resampling.LANCZOS)
            image.paste(picture, (596 - picture.width, 355 - picture.height))
    image.save(path, format="JPEG", quality=86, optimize=True)


# Obsidian image embeds are only a syntax convenience here. The file resolver
# still validates every path against explicit local scan roots; vault opening
# and wiki-style note links belong to M010.
_OBSIDIAN_IMAGE = re.compile(
    r"!\[\[([^\]|\n]+?\.(?:png|jpe?g|webp|gif))(?:\|[^\]\n]*)?\]\]",
    flags=re.IGNORECASE,
)


def _normalize_image_embeds(text: str) -> str:
    def convert(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        alt = Path(name).name.replace("[", "").replace("]", "")
        return "![" + alt + "](" + quote(name, safe="/._-") + ")"

    # Keep fenced code unchanged. CommonMark's fenced block token maps are
    # authoritative even when fences have uncommon lengths or markers.
    lines = text.splitlines(keepends=True)
    parser = _parser()
    blocked = set()
    for token in parser.parse(text):
        if token.type in {"fence", "code_block"} and token.map:
            blocked.update(range(token.map[0], token.map[1]))
    return "".join(
        line if index in blocked else _OBSIDIAN_IMAGE.sub(convert, line)
        for index, line in enumerate(lines)
    )


class _LocalImageAssets:
    """Only decode explicitly referenced local images from authorized roots.

    Images are re-encoded to a safe static format and saved in the *same*
    immutable generation as each Markdown document's HTML previews.
    """

    def __init__(self, source: Path, output: Path, roots: list[str | Path] | None) -> None:
        self.source = source.resolve()
        self.output = output
        self.roots = [
            Path(path).expanduser().resolve()
            for path in (roots if roots is not None else [source.parent])
        ]
        self.cached: dict[Path, str] = {}
        self.vault_root = next(
            (parent for parent in self.source.parents if (parent / ".obsidian").is_dir()),
            None,
        )
        self.first_in_section: Path | None = None
        self.total_bytes = 0

    def _resolve(self, raw: str) -> Path | None:
        if not raw or raw.startswith(("/", "\\")):
            return None
        try:
            parsed = urlsplit(raw)
        except ValueError:
            return None
        if parsed.scheme or parsed.netloc or not parsed.path:
            return None
        decoded = unquote(parsed.path)
        if "\x00" in decoded or "\\" in decoded or not decoded or re.match(r"^[A-Za-z]:", decoded):
            return None
        if Path(decoded).suffix.lower() not in _SAFE_IMAGE_SUFFIXES:
            return None
        candidate = (self.source.parent / decoded).resolve()
        # Obsidian commonly embeds vault-root-relative attachment paths.
        # This fallback does not perform any global filename/asset search.
        if not candidate.is_file() and self.vault_root is not None:
            candidate = (self.vault_root / decoded).resolve()
        if not any(candidate.is_relative_to(root) for root in self.roots):
            return None
        return candidate

    def __call__(self, raw: str) -> str | None:
        candidate = self._resolve(raw)
        if candidate is None:
            return None
        if candidate in self.cached:
            cached = self.cached[candidate]
            if self.first_in_section is None:
                self.first_in_section = self.output / cached
            return cached
        if len(self.cached) >= MAX_LOCAL_IMAGES:
            return None
        try:
            stat = candidate.stat()
            if not candidate.is_file() or not 0 < stat.st_size <= MAX_LOCAL_IMAGE_BYTES:
                return None
            if self.total_bytes + stat.st_size > MAX_TOTAL_IMAGE_BYTES:
                return None
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(candidate) as original:
                    if original.format not in _SAFE_IMAGE_FORMATS:
                        return None
                    if original.width * original.height > MAX_IMAGE_PIXELS:
                        return None
                    original.seek(0)  # animated formats get a safe static preview
                    image = ImageOps.exif_transpose(original).copy()
            self.total_bytes += stat.st_size
            image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            # Re-encode pixels; do not copy metadata or user-provided SVG/HTML.
            has_alpha = image.mode in ("RGBA", "LA") or "transparency" in image.info
            extension = "png" if has_alpha else "jpg"
            output_name = f"local_image_{len(self.cached) + 1:03d}.{extension}"
            output_file = self.output / output_name
            if has_alpha:
                image.convert("RGBA").save(output_file, format="PNG", optimize=True)
            else:
                image.convert("RGB").save(output_file, format="JPEG", quality=88, optimize=True)
            self.cached[candidate] = output_name
            if self.first_in_section is None:
                self.first_in_section = output_file
            return output_name
        except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError):
            return None


def render_markdown_snippets(
    source: str | Path, output_dir: str | Path,
    *, allowed_roots: list[str | Path] | None = None,
) -> list[dict]:
    """Render each Markdown section to a JPEG card and restricted local HTML."""
    source = Path(source)
    if source.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Markdown file exceeds the configured safety limit")
    text = _normalize_image_embeds(source.read_text(encoding="utf-8-sig"))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    parser = _parser()
    images = _LocalImageAssets(source, out, allowed_roots)
    result = []
    for number, (title, markdown_section) in enumerate(split_markdown(text, source.stem), 1):
        images.first_in_section = None
        body_html = parser.render(markdown_section, {"local_image_resolver": images})
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
        _thumbnail(out / thumb_name, title, text_value, number, images.first_in_section)
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
