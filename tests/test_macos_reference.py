"""M008d: deterministic PPTX fixtures and offline rendering comparison."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation

from ppt_visual_archive.extractor import extract_metadata


def _script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / name
    spec = importlib.util.spec_from_file_location("test_" + name.replace(".", "_"), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fixtures():
    return _script("build_macos_fixtures.py")


@pytest.fixture
def compare():
    return _script("compare_slide_images.py")


def _images(root: Path, colors):
    root.mkdir(parents=True)
    for i, color in enumerate(colors, start=1):
        Image.new("RGB", (90, 52), color).save(root / f"preview_{i:03d}.jpg", quality=100)


def test_reference_decks_have_original_text_notes_chart_image_and_hidden_slide(fixtures, tmp_path):
    result = fixtures.generate(tmp_path / "assets")
    assert sum(deck["slide_count"] for deck in result["decks"]) == 8
    assert len(result["decks"]) == 2
    for deck in result["decks"]:
        path = tmp_path / "assets" / deck["file"]
        assert path.is_file()
        meta = extract_metadata(str(path))
        assert meta["slide_count"] == deck["slide_count"]
        assert [slide["title"] for slide in meta["slides"]] == [
            slide["title"] for slide in deck["slides"]
        ]
        for i, slide in enumerate(deck["slides"]):
            assert slide["notes"] in meta["slides"][i]["notes_text"]

    main = Presentation(tmp_path / "assets" / "visual-rendering-baseline.pptx")
    assert main.slides[5]._element.get("show") == "0"
    assert any(getattr(shape, "has_chart", False) for shape in main.slides[3].shapes)
    assert any(getattr(shape, "has_table", False) for shape in main.slides[1].shapes)
    assert any(shape.shape_type == 13 for shape in main.slides[2].shapes)  # embedded picture


def test_fixture_generation_same_content_twice(fixtures, tmp_path):
    first = fixtures.generate(tmp_path / "a")
    second = fixtures.generate(tmp_path / "b")
    # ZIP hashes might include library timestamps; compare semantic manifest.
    for one, two in zip(first["decks"], second["decks"]):
        assert one["slides"] == two["slides"]
        assert one["slide_count"] == two["slide_count"]


def test_image_compare_identical_and_changed_images(compare, tmp_path):
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    _images(reference, [(12, 35, 59), (15, 40, 60)])
    _images(candidate, [(12, 35, 59), (240, 20, 20)])
    report = compare.compare_dirs(reference, candidate, max_mae=7)
    assert report["slide_count"] == 2
    assert report["slides"][0]["status"] == "ok"
    assert report["slides"][0]["mae"] == 0
    assert report["slides"][1]["status"] == "difference"
    assert report["slides"][1]["mae"] > 7
    assert report["mismatches"] == 1
    assert str(reference) not in json.dumps(report)
    html = compare.render_html(report, reference, candidate, max_preview=2)
    assert "data:image/png;base64," in html
    assert "Difference (enhanced)" in html
    assert str(reference) not in html


def test_comparison_flags_missing_extra_and_size_mismatch(compare, tmp_path):
    ref = tmp_path / "ref"
    cand = tmp_path / "cand"
    _images(ref, [(10, 20, 30), (50, 60, 70)])
    _images(cand, [(10, 20, 30), (50, 60, 70), (80, 90, 100)])
    (cand / "preview_002.jpg").unlink()
    report = compare.compare_dirs(ref, cand)
    assert [item["status"] for item in report["slides"]] == ["ok", "missing", "extra"]
    Image.new("RGB", (120, 30), (10, 20, 30)).save(cand / "preview_001.jpg")
    assert compare.compare_dirs(ref, cand)["slides"][0]["status"] == "size_mismatch"


def test_image_comparison_cli_writes_reports_and_strict_status(compare, tmp_path):
    reference = tmp_path / "ref"
    candidate = tmp_path / "candidate"
    out = tmp_path / "results"
    _images(reference, [(10, 20, 30)])
    _images(candidate, [(240, 100, 120)])
    argv = ["--reference", str(reference), "--candidate", str(candidate),
            "--output", str(out), "--max-mae", "0", "--fail-on-difference"]
    assert compare.main(argv) == 2
    payload = json.loads((out / "comparison.json").read_text())
    assert payload["mismatches"] == 1
    assert "data:image/png;base64" in (out / "comparison.html").read_text()
    assert compare.main(argv[:-1]) == 0


def test_comparison_does_not_accept_unsafe_or_ambiguous_paths(compare, tmp_path):
    ref = tmp_path / "ref"
    cand = tmp_path / "cand"
    _images(ref, [(10, 20, 30)])
    _images(cand, [(10, 20, 30)])
    Image.new("RGB", (90, 52)).save(ref / "preview_001.png")
    with pytest.raises(ValueError, match="Duplicate"):
        compare.compare_dirs(ref, cand)
    with pytest.raises(ValueError, match="kind"):
        compare.compare_dirs(cand, cand, kind="other")
