"""Safe, one-page US Letter JPEG previews for local Markdown documents.

CommonMark is parsed with raw HTML/active links disabled, and only explicitly
allowed, sanitized local images can enter the page layout. One physical Letter
page is rasterized; the entire document remains searchable. Sources are read-only.
"""
from __future__ import annotations

import html
import http.client
import ipaddress
import socket
import ssl
from contextlib import closing
import io
import re
import warnings
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from markdown_it import MarkdownIt
import fitz
from PIL import Image, ImageOps, UnidentifiedImageError

from .remote_image_cache import RemoteImageCache


MAX_SOURCE_BYTES = 16 * 1024 * 1024
# The PDF/Story layout uses physical points. At 96 dpi the preview is an
# 816 × 1056 px portrait US Letter image, never a multi-page output.
LETTER_WIDTH_PT = 612
LETTER_HEIGHT_PT = 792
LETTER_PREVIEW_PIXELS = (816, 1056)
LETTER_THUMB_PIXELS = (408, 528)
LETTER_MARGIN_PT = 45
MAX_LOCAL_IMAGES = 48
MAX_LOCAL_IMAGE_BYTES = 12 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 64 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
_SAFE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_SAFE_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}

# Only fixed author-controlled CSS is passed to PyMuPDF Story. Image sources
# in rendered HTML are exclusively generated file basenames from _LocalImageAssets.
_LETTER_CSS = """
body{font-family:sans-serif;font-size:11pt;line-height:1.35;color:#253046}
h1,h2,h3,h4,h5,h6{color:#1e293b;line-height:1.18;margin:11pt 0 6pt}
h1{font-size:19pt} h2{font-size:16pt} h3{font-size:13pt}
p,ul,ol,blockquote,table,pre{margin:0 0 9pt}
ul,ol{padding-left:18pt}
blockquote{margin-left:8pt;padding-left:10pt;border-left:2pt solid #cbd5e1}
pre{font-family:monospace;font-size:9pt;white-space:pre-wrap;padding:6pt;background:#f3f6fa}
code{font-family:monospace;font-size:9pt}
table{border-collapse:collapse;width:100%;font-size:9.5pt}
th,td{border:0.6pt solid #dce3ed;padding:4pt;text-align:left}
th{background:#f1f5f9}
.md-local-image{display:block;max-width:100%;max-height:245pt;width:auto;height:auto;margin:8pt 0}
.md-image-placeholder{color:#64748b;background:#f1f5f9}
.md-link{color:#28557f}
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


def _render_letter_page(fragment: str, output_dir: Path, preview_path: Path, thumb_path: Path) -> None:
    """Lay out *only* page one, then derive both JPEGs from identical pixels.

    Unlike a character/heading budget, Story.place() obeys actual image sizes,
    line wrapping and block height. Content beyond the first Letter page is not
    drawn or rasterized, even though it remains indexed for text search.
    """
    buffer = io.BytesIO()
    story = fitz.Story(
        html=fragment, user_css=_LETTER_CSS, em=11,
        archive=fitz.Archive(str(output_dir)),
    )
    writer = fitz.DocumentWriter(buffer)
    try:
        device = writer.begin_page(fitz.Rect(0, 0, LETTER_WIDTH_PT, LETTER_HEIGHT_PT))
        story.place(fitz.Rect(
            LETTER_MARGIN_PT, LETTER_MARGIN_PT,
            LETTER_WIDTH_PT - LETTER_MARGIN_PT,
            LETTER_HEIGHT_PT - LETTER_MARGIN_PT,
        ))
        story.draw(device)
        writer.end_page()
    finally:
        writer.close()
    # The in-memory PDF never becomes an exported asset. Only the first page is
    # opened, even if the source contains enough content for hundreds of pages.
    with fitz.open(stream=buffer.getvalue(), filetype="pdf") as document:
        pixels = document[0].get_pixmap(
            matrix=fitz.Matrix(4 / 3, 4 / 3), colorspace=fitz.csRGB,
            alpha=False,
        )
        with Image.frombytes("RGB", (pixels.width, pixels.height), pixels.samples) as first:
            if first.size != LETTER_PREVIEW_PIXELS:
                raise RuntimeError("Letter preview dimensions differ from physical page geometry")
            first.save(preview_path, format="JPEG", quality=87, optimize=True)
            thumbnail = first.resize(LETTER_THUMB_PIXELS, Image.Resampling.LANCZOS)
            try:
                thumbnail.save(thumb_path, format="JPEG", quality=86, optimize=True)
            finally:
                thumbnail.close()


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


def _valid_public_hostname(host: str) -> bool:
    """Require a conventional public DNS name, never a literal IP or local zone."""
    if len(host) > 253 or not re.fullmatch(
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?",
        host,
    ):
        return False
    if host.endswith((".local", ".localhost", ".internal", ".test", ".invalid",
                      ".example", ".onion", ".home.arpa")):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return True


class _PinnedPublicHTTPSConnection(http.client.HTTPSConnection):
    """Connect to validated public IP, preserving the original hostname and TLS SNI."""

    def __init__(self, host: str, address: str):
        super().__init__(host, 443, timeout=4)
        self._pinned_address = address

    def connect(self) -> None:
        plain = socket.create_connection((self._pinned_address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(plain, server_hostname=self.host)
        except BaseException:
            plain.close()
            raise


def _parse_public_https_url(raw: str) -> tuple[str, str] | None:
    """Validate URL structure *before* a cache lookup or DNS request."""
    if len(raw) > 4096 or any(ord(c) < 32 for c in raw) or "\\" in raw:
        return None
    try:
        url = urlsplit(raw)
        host = (url.hostname or "").lower()
        if (
            url.scheme != "https" or not _valid_public_hostname(host)
            or url.username is not None or url.password is not None
            or url.port not in (None, 443)
            or (url.path and not url.path.startswith("/"))
        ):
            return None
        target = url.path or "/"
        if url.query:
            target += "?" + url.query
        return host, target
    except (ValueError, UnicodeError):
        return None


def _fetch_public_https_image(raw: str) -> bytes | None:
    """Bounded public-only HTTPS fetch; no proxy, redirects, local DNS or credentials."""
    target = _parse_public_https_url(raw)
    if target is None:
        return None
    host, path = target
    try:
        # A mixed public/private DNS answer is treated as unsafe, not selectively used.
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
        if not addresses or not all(ipaddress.ip_address(ip).is_global for ip in addresses):
            return None
        with closing(_PinnedPublicHTTPSConnection(host, addresses[0])) as conn:
            conn.request("GET", path, headers={
                "Accept": "image/jpeg,image/png,image/webp,image/gif",
                "User-Agent": "PowerPointVisualArchive/MarkdownImage",
            })
            response = conn.getresponse()
            if response.status != 200:  # never follow 3xx redirects
                return None
            media = (response.getheader("content-type") or "").split(";", 1)[0].strip().lower()
            if media not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
                return None
            size = response.getheader("content-length")
            if size is not None and int(size) > MAX_LOCAL_IMAGE_BYTES:
                return None
            data = response.read(MAX_LOCAL_IMAGE_BYTES + 1)
            return data if 0 < len(data) <= MAX_LOCAL_IMAGE_BYTES else None
    except (OSError, ValueError, UnicodeError, http.client.HTTPException, ssl.SSLError):
        return None


class _LocalImageAssets:
    """Only decode explicitly referenced local images from authorized roots.

    Images are re-encoded to a safe static format and saved in the *same*
    immutable generation as each Markdown document's HTML previews.
    """

    def __init__(self, source: Path, output: Path, roots: list[str | Path] | None,
                 *, offline_mode: bool = False, remote_cache_dir: str | Path | None = None) -> None:
        self.source = source.resolve()
        self.output = output
        self.roots = [
            Path(path).expanduser().resolve()
            for path in (roots if roots is not None else [source.parent])
        ]
        self.cached: dict[Path | str, str] = {}
        if not isinstance(offline_mode, bool):
            raise ValueError("markdown_offline_mode must be boolean")
        self.offline_mode = offline_mode
        self.remote_cache = RemoteImageCache(remote_cache_dir) if not offline_mode else None
        self.vault_root = next(
            (parent for parent in self.source.parents if (parent / ".obsidian").is_dir()),
            None,
        )
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
        try:
            parsed = urlsplit(raw)
        except ValueError:
            return None
        remote = bool(parsed.scheme or parsed.netloc or raw.startswith("//"))
        if remote:
            if self.offline_mode or _parse_public_https_url(raw) is None:
                return None
            key: Path | str = raw
        else:
            candidate = self._resolve(raw)
            if candidate is None:
                return None
            key = candidate
        if key in self.cached:
            return self.cached[key]
        if len(self.cached) >= MAX_LOCAL_IMAGES:
            return None
        try:
            downloaded = False
            if remote:
                try:
                    cache_hit = self.remote_cache.get(raw) if self.remote_cache else None
                except OSError:
                    cache_hit = None
                if cache_hit is not None:
                    input_asset = cache_hit
                    data_size = cache_hit.stat().st_size
                else:
                    payload = _fetch_public_https_image(raw)
                    if payload is None:
                        return None
                    input_asset = io.BytesIO(payload)
                    data_size = len(payload)
                    downloaded = True
            else:
                stat = candidate.stat()
                if not candidate.is_file() or not 0 < stat.st_size <= MAX_LOCAL_IMAGE_BYTES:
                    return None
                data_size = stat.st_size
                input_asset = candidate
            if self.total_bytes + data_size > MAX_TOTAL_IMAGE_BYTES:
                return None
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(input_asset) as original:
                    if original.format not in _SAFE_IMAGE_FORMATS:
                        return None
                    if original.width * original.height > MAX_IMAGE_PIXELS:
                        return None
                    original.seek(0)
                    image = ImageOps.exif_transpose(original).copy()
            try:
                image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                has_alpha = image.mode in ("RGBA", "LA") or "transparency" in image.info
                extension = "png" if has_alpha else "jpg"
                output_name = f"local_image_{len(self.cached) + 1:03d}.{extension}"
                output_file = self.output / output_name
                if has_alpha:
                    image.convert("RGBA").save(output_file, format="PNG", optimize=True)
                else:
                    image.convert("RGB").save(output_file, format="JPEG", quality=88, optimize=True)
            finally:
                image.close()
            if downloaded and self.remote_cache:
                try:
                    self.remote_cache.put(raw, output_file)
                except OSError:
                    pass  # an unwritable cache must not hide a valid rendered image
            self.total_bytes += data_size
            self.cached[key] = output_name
            return output_name
        except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError):
            return None


def render_markdown_snippets(
    source: str | Path, output_dir: str | Path,
    *, allowed_roots: list[str | Path] | None = None,
    offline_mode: bool = False,
    remote_image_cache_dir: str | Path | None = None,
) -> list[dict]:
    """Generate exactly one physical Letter preview for the first page of a note.

    The existing pipeline method name is retained for source compatibility.
    Full-document text goes into SQLite search; only page-one pixels enter the
    JPEG preview/thumbnail. Existing HTML previews stay browseable in the UI.
    """
    source = Path(source)
    if source.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Markdown file exceeds the configured safety limit")
    content = _remove_yaml_frontmatter(source.read_text(encoding="utf-8-sig"))
    content = _normalize_image_embeds(content)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    parser = _parser()
    images = _LocalImageAssets(
        source, out, allowed_roots, offline_mode=offline_mode,
        remote_cache_dir=remote_image_cache_dir,
    )
    # No heading splitting. HTML is transient and rendered only by the trusted
    # local Story layout engine, never served to the browser.
    page_html = parser.render(content, {"local_image_resolver": images})
    full_text = _text_from_html(page_html)
    preview_name, thumb_name = "preview_001.jpg", "thumb_001.jpg"
    try:
        _render_letter_page(page_html, out, out / preview_name, out / thumb_name)
    finally:
        # The first-page raster embeds every visible image; temporary sanitized
        # input assets are not needed in the final immutable generation.
        for filename in images.cached.values():
            (out / filename).unlink(missing_ok=True)
    return [{
        "slide_number": 1,
        "title": source.stem or "Untitled note",
        "body_text": full_text,
        "extracted_text": full_text,
        "thumb_path": thumb_name,
        "preview_path": preview_name,
        "width": LETTER_PREVIEW_PIXELS[0],
        "height": LETTER_PREVIEW_PIXELS[1],
    }]
