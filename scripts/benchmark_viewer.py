"""Repeatable browser workload for the local visual archive (synthetic data only).

Usage:
  python scripts/benchmark_viewer.py --slides 6000 20000 --iterations 5
  python scripts/benchmark_viewer.py --slides 120 --iterations 2 --output-dir .runtime/benchmarks

Requires project Python dependencies, Node.js >=22 and Chromium/Chrome/Edge.
Outputs locally stored JSON, with no real presentation data or source paths.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image, ImageDraw

from benchmark_large_archive import build_fixture

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".runtime" / "benchmarks"


def locate_browser(requested: str | None = None) -> str:
    if requested:
        result = shutil.which(requested) or (requested if Path(requested).is_file() else None)
        if not result:
            raise ValueError(f"Browser not found: {requested}")
        return result
    for command in ("chromium", "chromium-browser", "google-chrome", "chrome", "msedge"):
        found = shutil.which(command)
        if found:
            return found
    raise ValueError("Chromium/Chrome/Edge not found; set --browser to its executable path")


def git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, timeout=4
        ).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"


def working_tree_dirty() -> bool:
    """Distinguish a committed baseline from an uncommitted development run."""
    try:
        return bool(subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT, text=True, timeout=4,
        ).strip())
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return True


def prepare_synthetic_site(output: Path, *, slides: int, text_chars: int) -> dict:
    """Generate the exact real viewer frontend plus a deterministic fake archive."""
    output.mkdir(parents=True, exist_ok=True)
    data = build_fixture(slide_count=slides, text_chars=text_chars)
    for source_dir in ("css", "js"):
        shutil.copytree(ROOT / "web" / "static" / source_dir, output / source_dir)

    # Deliberately shared JPEG placeholders: search/DOM regressions are measured,
    # but thumbnail decoding/network performance is NOT representative.
    (output / "assets").mkdir()
    image = Image.new("RGB", (384, 216), (226, 231, 241))
    ImageDraw.Draw(image).text((15, 25), "Synthetic benchmark slide", fill=(40, 55, 75))
    image.save(output / "assets" / "thumbnail.jpg", format="JPEG", quality=80)
    image.save(output / "assets" / "preview.jpg", format="JPEG", quality=90)
    for slide in data["slides"]:
        slide["thumb"] = "assets/thumbnail.jpg"
        slide["preview"] = "assets/preview.jpg"

    env = Environment(loader=FileSystemLoader(str(ROOT / "web" / "templates")), autoescape=True)
    html = env.get_template("index.html.j2").render(
        title="Synthetic PowerPoint Archive Benchmark",
        generated_at="synthetic fixture",
        stats=data["stats"],
    )
    (output / "index.html").write_text(html, encoding="utf-8")
    (output / "data").mkdir()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    (output / "data" / "export.json").write_bytes(payload)
    return {"slide_count": len(data["slides"]), "deck_count": len(data["decks"]), "json_bytes": len(payload), "text_chars": text_chars}


def run_scenario(
    *,
    slides: int,
    text_chars: int,
    iterations: int,
    browser: str,
    node: str,
    timeout_seconds: int,
) -> dict:
    with tempfile.TemporaryDirectory(prefix="pptviewer-benchmark-") as tmp:
        fixture = prepare_synthetic_site(Path(tmp) / "site", slides=slides, text_chars=text_chars)
        completed = subprocess.run(
            [node, str(ROOT / "scripts" / "measure_viewer.mjs"),
             browser, str(Path(tmp) / "site"), str(iterations), str(timeout_seconds)],
            cwd=ROOT, capture_output=True, text=True, timeout=timeout_seconds + 35,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "Browser workload failed (exit " + str(completed.returncode) + "): "
                + completed.stderr[-2000:]
            )
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("No valid browser benchmark report produced") from exc
        if result["library_slides"] != slides or result["max_visible_cards"] > 240:
            raise RuntimeError("Benchmark invariant failed: archive size or DOM bound")
        return {"fixture": fixture, **result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slides", nargs="+", type=int, default=[6000, 20000])
    parser.add_argument("--text-chars", type=int, default=1000)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--browser", help="Chromium/Chrome/Edge executable; auto-detect by default")
    parser.add_argument("--node", default="node", help="Node.js >=22 executable")
    parser.add_argument("--timeout-seconds", type=int, default=90)
    args = parser.parse_args(argv)

    if any(s < 1 for s in args.slides) or args.text_chars < 0 or args.iterations < 1:
        parser.error("slide counts, text length and iterations must be non-negative (slides/iterations >0)")
    if args.timeout_seconds < 10:
        parser.error("--timeout-seconds must be at least 10")
    browser = locate_browser(args.browser)
    node = shutil.which(args.node) or (args.node if Path(args.node).is_file() else None)
    if node is None:
        parser.error("Node.js >=22 is required for the browser workload")
    node_version = subprocess.check_output([node, "--version"], text=True).strip()
    if int(node_version.lstrip("v").split(".")[0]) < 22:
        parser.error("Node.js >=22 is required (found " + node_version + ")")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    revision = git_revision()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for slide_count in args.slides:
        print(f"Measuring {slide_count:,} synthetic slides ({args.iterations} searches)...", flush=True)
        measured = run_scenario(
            slides=slide_count, text_chars=args.text_chars,
            iterations=args.iterations, browser=browser, node=node,
            timeout_seconds=args.timeout_seconds,
        )
        result = {
            "schema_version": 1,
            "scenario": "synthetic-viewer",
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "git_revision": revision,
            "working_tree_dirty": working_tree_dirty(),
            "platform": {"system": platform.system(), "architecture": platform.machine()},
            "node_version": node_version,
            "measurement": measured,
        }
        path = args.output_dir / f"viewer-{slide_count}-{revision}-{stamp}.json"
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        timings = measured["browser_report"]["timings"]
        initial = timings.get("startup.interactive_ms", {}).get("p50_ms")
        search = timings.get("interaction.filter_to_grid_ms", {}).get("p95_ms")
        print(f"  initial={initial} ms  filter-to-grid p95={search} ms  "
              f"cards={measured['max_visible_cards']}  report={path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
