"""Generate original, nonproprietary PowerPoint decks for renderer acceptance.

Run:
  python scripts/build_macos_fixtures.py --output .runtime/mac-reference

No native renderer is used; these PPTX files are intended to be processed on
Windows and macOS later. Expected titles/notes and hidden-slide flags are stored
in a small manifest for automatic verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt


def _slide(prs: Presentation, title: str, notes: str, *, hidden: bool = False):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = title
    slide.notes_slide.notes_text_frame.text = notes
    if hidden:
        # OOXML p:sld show="0" corresponds to PowerPoint's hidden-slide flag.
        slide._element.set("show", "0")
    return slide


def _picture(path: Path) -> None:
    image = Image.new("RGB", (640, 360), (247, 248, 251))
    draw = ImageDraw.Draw(image)
    for x in range(0, 640, 20):
        shade = int(50 + 155 * x / 640)
        draw.rectangle((x, 0, x + 20, 360), fill=(shade, 130, 230 - shade // 3))
    draw.ellipse((235, 65, 415, 245), fill=(255, 234, 122), outline=(36, 55, 80), width=9)
    draw.text((40, 290), "Original embedded-image fixture", fill=(25, 30, 35))
    image.save(path, format="PNG")


def _visual_deck(out: Path) -> tuple[Path, dict]:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    manifest: dict = {"slide_count": 6, "slides": []}

    def add(slide, title, notes, feature, hidden=False):
        manifest["slides"].append({
            "number": len(manifest["slides"]) + 1,
            "title": title, "notes": notes, "feature": feature, "hidden": hidden,
        })
        return slide

    a = _slide(prs, "01 / Colored vector shapes", "Speaker notes: vector regression.")
    shape = a.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1), Inches(1.5), Inches(6), Inches(3))
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(24, 105, 189)
    shape.line.color.rgb = RGBColor(225, 95, 85)
    add(a, "01 / Colored vector shapes", "Speaker notes: vector regression.", "vector-shapes")

    b = _slide(prs, "02 / Table and aligned numbers", "Speaker notes: four columns.")
    table = b.shapes.add_table(3, 4, Inches(1), Inches(1.4), Inches(10), Inches(3)).table
    for col, label in enumerate(("Period", "North", "South", "Total")):
        table.cell(0, col).text = label
    for row in (1, 2):
        for col in range(4):
            table.cell(row, col).text = str(row * 100 + col)
    add(b, "02 / Table and aligned numbers", "Speaker notes: four columns.", "table")

    c = _slide(prs, "03 / Embedded image", "Speaker notes: picture placement.")
    image_path = out / "_embedded-image.png"
    _picture(image_path)
    c.shapes.add_picture(str(image_path), Inches(1), Inches(1.45), width=Inches(10))
    add(c, "03 / Embedded image", "Speaker notes: picture placement.", "picture")

    d = _slide(prs, "04 / Native PowerPoint chart", "Speaker notes: chart objects.")
    data = CategoryChartData()
    data.categories = ["Alpha", "Beta", "Gamma"]
    data.add_series("2025", (12, 22, 32))
    data.add_series("2026", (16, 26, 36))
    d.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(0.7), Inches(1.2), Inches(11.7), Inches(5.4), data,
    )
    add(d, "04 / Native PowerPoint chart", "Speaker notes: chart objects.", "chart")

    e = _slide(prs, "05 / Unicode typography — 日本語 / München / café", "Speaker notes: unicode and font substitution.")
    box = e.shapes.add_textbox(Inches(1), Inches(1.6), Inches(11), Inches(3))
    p = box.text_frame.paragraphs[0]
    run = p.add_run()
    run.text = "日本語 · Ελληνικά · Café · Größe · 東京"
    run.font.name = "Aptos"
    run.font.size = Pt(26)
    run.font.color.rgb = RGBColor(31, 54, 110)
    add(e, "05 / Unicode typography — 日本語 / München / café",
        "Speaker notes: unicode and font substitution.", "unicode-font")

    f = _slide(prs, "06 / Intentionally hidden slide", "Speaker notes: verify hidden slides.", hidden=True)
    shape = f.shapes.add_shape(MSO_SHAPE.HEXAGON, Inches(3), Inches(2), Inches(4), Inches(3))
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(190, 80, 115)
    add(f, "06 / Intentionally hidden slide", "Speaker notes: verify hidden slides.", "hidden", True)

    output = out / "visual-rendering-baseline.pptx"
    prs.save(output)
    image_path.unlink()
    return output, manifest


def _control_deck(out: Path) -> tuple[Path, dict]:
    prs = Presentation()
    titles = ["Simple title and subtitle", "Second slide for page ordering"]
    notes = ["Speaker notes: control slide one.", "Speaker notes: control slide two."]
    expected = []
    for number, title in enumerate(titles, start=1):
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = title
        slide.placeholders[1].text = "Text is read directly from the PPTX."
        slide.notes_slide.notes_text_frame.text = notes[number - 1]
        expected.append({"number": number, "title": title, "notes": notes[number - 1], "hidden": False,
                         "feature": "control"})
    path = out / "simple-control.pptx"
    prs.save(path)
    return path, {"slide_count": len(titles), "slides": expected}


def generate(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    for maker in (_visual_deck, _control_deck):
        file, meta = maker(output)
        entries.append({
            "file": file.name,
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            **meta,
        })
    report = {
        "schema_version": 1,
        "description": "Generated PowerPoint image/text/notes/hidden slide acceptance fixture",
        "decks": entries,
        "rendering": {
            "expected_fidelity": "Compare actual PowerPoint-for-Mac versus Windows images",
            "hidden_slide_pdf_page_count": "unverified: PowerPoint export may omit hidden slide",
        },
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".runtime/mac-reference"))
    args = parser.parse_args(argv)
    report = generate(args.output)
    print("Generated", len(report["decks"]), "PowerPoint reference decks with",
          sum(d["slide_count"] for d in report["decks"]), "slides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
