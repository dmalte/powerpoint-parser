"""Opt-in native PowerPoint-for-Mac acceptance smoke test.

Run on the signed-in Mac:
    python scripts/smoke_macos_powerpoint.py --backend powerpoint --timeout 25

Creates original test PPTX if necessary, then renders via the real macOS
adapter. Reports only numeric metrics and error codes, not source paths.
No app/login installation or cloud uploads. May open PowerPoint and trigger
an Automation/File Access prompt; run from an unlocked user session.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
from ppt_visual_archive.config import RenderConfig
from ppt_visual_archive.extractor import extract_metadata


def run_smoke(source: Path, image_dir: Path, backend: str, timeout: int) -> dict:
    from ppt_visual_archive.mac_renderer import LibreOfficeRenderer, MacPowerPointRenderer

    started = time.perf_counter()
    report = {
        "schema_version": 1,
        "kind": "native_mac_powerpoint_render_smoke",
        "backend": backend,
        "status": "fail",
        "expected_slides": None,
        "rendered_slides": 0,
        "elapsed_ms": None,
        "office_error_code": None,
        "reason": None,
        "native_macos": sys.platform == "darwin",
    }
    if sys.platform != "darwin":
        report["reason"] = "Requires a native macOS interactive session"
        return report

    renderer_cls = MacPowerPointRenderer if backend == "powerpoint" else LibreOfficeRenderer
    try:
        metadata = extract_metadata(str(source))
        expected = metadata.get("slide_count", 0)
        if expected < 1:
            raise RuntimeError("Reference presentation has no valid slides")
        report["expected_slides"] = expected
        renderer = renderer_cls(RenderConfig(pptx_conversion_timeout_seconds=timeout))
        renderer.start()
        try:
            slides = renderer.export_slides(str(source), str(image_dir))
        finally:
            renderer.stop()
        report["rendered_slides"] = len(slides)
        if len(slides) != expected:
            raise RuntimeError("Rendered slide count differs from original PPTX")
        for record in slides:
            for key in ("thumb_path", "preview_path"):
                with Image.open(image_dir / record[key]) as rendered:
                    rendered.verify()
        report["status"] = "pass"
    except Exception as exc:
        report["reason"] = str(exc)[:350]
        cause = getattr(exc, "__cause__", None)
        if isinstance(cause, subprocess.CalledProcessError):
            codes = re.findall(r"-[0-9]{2,6}", cause.stderr or "")
            if codes:
                report["office_error_code"] = codes[-1]
    finally:
        report["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["powerpoint", "libreoffice"], default="powerpoint")
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--source", type=Path, help="Optional real PPTX; defaults to generated two-slide test")
    parser.add_argument("--output", type=Path, default=Path(".runtime/mac-native/pptx-smoke"))
    args = parser.parse_args(argv)
    if args.timeout < 5 or args.timeout > 180:
        parser.error("timeout must be between 5 and 180 seconds")
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.source
    if source is None:
        from build_macos_fixtures import generate

        fixture_dir = args.output / "fixtures"
        generate(fixture_dir)
        source = fixture_dir / "simple-control.pptx"
    results = run_smoke(source, args.output / "images", args.backend, args.timeout)
    (args.output / "result.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("Mac PowerPoint rendering:", results["status"],
          "slides:", results["rendered_slides"],
          "Office code:", results["office_error_code"] or "none")
    print("Path-free diagnostic report saved locally.")
    return 0 if results["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
