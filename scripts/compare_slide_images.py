"""Offline PowerPoint slide-image comparison for Mac versus Windows renderers.

Provide one deck generation directory per side. Files must be named
preview_001.jpg or thumb_001.jpg (PNG is also supported).

  python scripts/compare_slide_images.py --reference DIR --candidate DIR \
      --kind preview --max-mae 12 --output .runtime/image-comparison

Writes JSON numeric results and self-contained HTML with reference/candidate/
difference thumbnails. No cloud uploads or original documents are copied.
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, ImageStat

VALID_KINDS = ("preview", "thumb")
VALID_EXTS = {".jpg", ".jpeg", ".png"}


def _images(root: Path, kind: str) -> dict[int, Path]:
    if not root.is_dir():
        raise ValueError("Reference or candidate image directory is missing")
    pattern = re.compile(r"^" + re.escape(kind) + r"_(\d+)\.(jpg|jpeg|png)$", re.IGNORECASE)
    mapping: dict[int, Path] = {}
    for path in root.iterdir():
        if not path.is_file():
            continue
        match = pattern.fullmatch(path.name)
        if not match:
            continue
        number = int(match.group(1))
        if number < 1 or number in mapping:
            raise ValueError("Duplicate or invalid numbered slide image")
        mapping[number] = path
    if not mapping:
        raise ValueError("No correctly numbered slide images found")
    return mapping


def compare_dirs(reference: Path, candidate: Path, *, kind: str = "preview",
                 max_mae: float = 12.0) -> dict:
    if kind not in VALID_KINDS:
        raise ValueError("Image kind must be preview or thumb")
    if not 0 <= max_mae <= 255:
        raise ValueError("MAE threshold must be within 0–255")
    left = _images(reference, kind)
    right = _images(candidate, kind)
    rows = []
    for slide in sorted(set(left) | set(right)):
        entry = {"slide": slide, "status": "ok", "mae": None,
                 "changed_pct": None, "reference_size": None, "candidate_size": None}
        if slide not in left:
            entry["status"] = "extra"
        elif slide not in right:
            entry["status"] = "missing"
        else:
            with Image.open(left[slide]) as raw_a, Image.open(right[slide]) as raw_b:
                a, b = raw_a.convert("RGB"), raw_b.convert("RGB")
            entry["reference_size"] = [a.width, a.height]
            entry["candidate_size"] = [b.width, b.height]
            if a.size != b.size:
                entry["status"] = "size_mismatch"
            else:
                difference = ImageChops.difference(a, b)
                entry["mae"] = round(sum(ImageStat.Stat(difference).mean) / 3, 3)
                histogram = difference.convert("L").histogram()
                entry["changed_pct"] = round(100 * sum(histogram[6:]) / (a.width * a.height), 2)
                if entry["mae"] > max_mae:
                    entry["status"] = "difference"
        rows.append(entry)
    mismatches = sum(row["status"] != "ok" for row in rows)
    return {
        "schema_version": 1, "kind": kind,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold_mae": max_mae, "slide_count": len(rows),
        "mismatches": mismatches, "slides": rows,
        "note": "Per-slide pixel differences after native rendering; no source paths or image contents in JSON",
    }


def _thumbnail_data(path: Path | None) -> str:
    if not path:
        return ""
    with Image.open(path) as image:
        png = image.convert("RGB")
        png.thumbnail((420, 245))
        buffer = io.BytesIO()
        png.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _difference_data(a_path: Path | None, b_path: Path | None) -> str:
    if not a_path or not b_path:
        return ""
    with Image.open(a_path) as aa, Image.open(b_path) as bb:
        a, b = aa.convert("RGB"), bb.convert("RGB")
    if a.size != b.size:
        return ""
    delta = ImageChops.difference(a, b)
    # Amplify subtle JPEG variance for visual inspection, not scoring.
    visible = ImageOps.autocontrast(delta)
    visible.thumbnail((420, 245))
    buffer = io.BytesIO()
    visible.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def render_html(report: dict, reference: Path, candidate: Path,
                *, max_preview: int = 12) -> str:
    left = _images(reference, report["kind"])
    right = _images(candidate, report["kind"])
    headers = """<tr><th>Slide</th><th>Status</th><th>MAE (0–255)</th>
<th>Changed pixels (&gt;5)</th><th>Reference dimensions</th><th>Candidate dimensions</th></tr>"""
    rows = []
    samples = []
    for idx, record in enumerate(report["slides"]):
        status = html.escape(record["status"])
        rows.append(
            "<tr><td>" + str(record["slide"]) + '</td><td class="' + status + '">' + status
            + "</td><td>" + (str(record["mae"]) if record["mae"] is not None else "—")
            + "</td><td>" + (str(record["changed_pct"]) if record["changed_pct"] is not None else "—")
            + "</td><td>" + html.escape(str(record["reference_size"]))
            + "</td><td>" + html.escape(str(record["candidate_size"])) + "</td></tr>"
        )
        if idx >= max_preview:
            continue
        number = record["slide"]
        images = []
        for caption, uri in (
            ("Reference", _thumbnail_data(left.get(number))),
            ("Candidate", _thumbnail_data(right.get(number))),
            ("Difference (enhanced)", _difference_data(left.get(number), right.get(number))),
        ):
            images.append(
                "<div><small>" + caption + "</small>" +
                ('<img alt="' + caption + '" src="' + uri + '">' if uri else "<p>Not available</p>") +
                "</div>"
            )
        samples.append("<section><h3>Slide " + str(number) + " — " + status
                       + "</h3><div class=triplet>" + "".join(images) + "</div></section>")
    return """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>PowerPoint Rendering Comparison</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font:14px/1.5 system-ui,sans-serif;max-width:1360px;margin:25px auto;padding:0 24px;color:#26374a}
h1{font-size:23px}table{width:100%;border-collapse:collapse}th,td{padding:8px;text-align:left;border-bottom:1px solid #dde5ed}
th{background:#f5f7f9}.difference,.missing,.extra,.size_mismatch{color:#a03a21;font-weight:700}
.triplet{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.triplet img{width:100%;height:auto}
.triplet div{padding:10px;border:1px solid #dde5ed;border-radius:8px}section{margin:20px 0}
.note{color:#56677a}</style></head><body>
<h1>PowerPoint slide rendering comparison</h1>
<p>""" + html.escape(report["kind"]) + " — " + str(report["slide_count"]) + " slides, " + str(report["mismatches"]) + """ differences / missing images. Mean absolute error warning threshold: """ + str(report["threshold_mae"]) + """ per channel (0–255).</p>
<p class=note>Offline Mac/Windows acceptance aid. It compares already-rendered images, not textual contents. Different fonts, raster sizes or hidden-slide export rules may require manual review.</p>
<table>""" + headers + "".join(rows) + "</table>" + "".join(samples) + "</body></html>"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--kind", choices=VALID_KINDS, default="preview")
    parser.add_argument("--max-mae", type=float, default=12)
    parser.add_argument("--max-preview", type=int, default=12)
    parser.add_argument("--output", type=Path, default=Path(".runtime/image-comparison"))
    parser.add_argument("--fail-on-difference", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = compare_dirs(args.reference, args.candidate,
                              kind=args.kind, max_mae=args.max_mae)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "comparison.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8",
        )
        (args.output / "comparison.html").write_text(
            render_html(report, args.reference, args.candidate,
                        max_preview=max(0, args.max_preview)), encoding="utf-8",
        )
    except (ValueError, OSError) as exc:
        # Avoid leaking local input paths via generic OS exception messages.
        print("Could not compare the supplied render directories.")
        return 1
    print(f"Compared {report['slide_count']} slides: {report['mismatches']} differences.")
    print("Saved offline comparison.json and comparison.html.")
    return 2 if args.fail_on_difference and report["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
