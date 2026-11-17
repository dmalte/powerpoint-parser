"""Deterministic fixture and optional Chromium integration for M007a."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "scripts" / "benchmark_viewer.py"


def _load_runner():
    # Make sibling benchmark_large_archive.py discoverable when loaded by importlib.
    sys.path.insert(0, str(BENCHMARK.parent))
    spec = importlib.util.spec_from_file_location("benchmark_viewer", BENCHMARK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_benchmark_prepares_genuine_viewer_with_synthetic_data(tmp_path):
    runner = _load_runner()
    fixture = runner.prepare_synthetic_site(tmp_path / "site", slides=250, text_chars=80)
    assert fixture["slide_count"] == 250
    assert fixture["deck_count"] == 9
    output = tmp_path / "site"
    archive = json.loads((output / "data" / "export.json").read_text())
    assert len(archive["slides"]) == 250
    assert archive["slides"][0]["thumb"] == "assets/thumbnail.jpg"
    assert (output / "assets" / "thumbnail.jpg").is_file()
    assert (output / "js" / "performance.js").is_file()
    assert (output / "js" / "agent-status.js").is_file()
    assert (output / "js" / "deck-pager.js").is_file()
    assert 'id="slide-grid"' in (output / "index.html").read_text()
    assert "source_path" not in json.dumps(fixture)


def test_profile_memory_mode_reports_retained_heap_without_source_content(tmp_path):
    runner = _load_runner()
    try:
        browser = runner.locate_browser()
    except ValueError:
        pytest.skip("No Chromium-family browser available")
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js >=22 is not installed")
    version = subprocess.check_output([node, "--version"], text=True)
    if int(version.lstrip("v").split(".")[0]) < 22:
        pytest.skip("Node.js >=22 is required for memory profiling")
    site = tmp_path / "site"
    runner.prepare_synthetic_site(site, slides=120, text_chars=125)
    process = subprocess.run(
        [node, str(ROOT / "scripts/measure_viewer.mjs"),
         browser, str(site), "2", "45", "--profile-memory"],
        capture_output=True, text=True, timeout=55,
    )
    assert process.returncode == 0, process.stderr[-900:]
    report = json.loads(process.stdout)
    profile = report["memory_profile"]
    assert profile["initial_retained_heap_mb"] > 0
    assert profile["post_search_retained_heap_mb"] > 0
    assert report["library_slides"] == 120
    assert "benchmark x" not in process.stdout  # no synthetic search or slide content
    assert "source_path" not in process.stdout


def test_browser_benchmark_cdp_integration(tmp_path):
    runner = _load_runner()
    browser = None
    try:
        browser = runner.locate_browser()
    except ValueError:
        pytest.skip("No local Chromium-family browser available")
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js >=22 is not installed")
    version = subprocess.check_output([node, "--version"], text=True)
    if int(version.lstrip("v").split(".")[0]) < 22:
        pytest.skip("Node.js >=22 is required for the CDP harness")
    result = runner.run_scenario(
        slides=3150,
        text_chars=80,
        iterations=2,
        browser=browser,
        node=node,
        timeout_seconds=45,
    )
    assert result["fixture"]["slide_count"] == 3150
    assert result["sidebar_rows_initial"] == 100
    assert result["sidebar_rows_final"] <= 100
    assert result["sidebar_verification"]["passed"] is True
    assert result["sidebar_verification"]["pages_checked"] == 2
    assert result["search_scope_verification"] == {"passed": True, "tested": 9, "restored": True}
    assert result["max_visible_cards"] == 240
    assert result["scripted_actions"]["searches"] == 2
    assert result["browser_report"]["library"]["slides"] == 3150
    assert "startup.interactive_ms" in result["browser_report"]["timings"]
    assert "interaction.search_filter_ms" in result["browser_report"]["timings"]
    assert "interaction.sort_ms" in result["browser_report"]["timings"]
    assert "grid.render_ms" in result["browser_report"]["timings"]
    assert isinstance(result["browser_version"], str)
