"""Deterministic tests for M007d revision comparisons and offline reports."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("benchmark_history", ROOT / "scripts" / "benchmark_history.py")
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
assert SPEC.loader
SPEC.loader.exec_module(module)


def sample(revision: str, stamp: str, *, slides: int = 6000, browser: str = "Chrome/100",
           dirty: bool = False, search_count: int = 8, p95: float = 20.0,
           startup: float = 200.0, title: str = "source", text_chars: int = 1000):
    timing = {
        "startup.interactive_ms": {"p50_ms": startup, "count": 1},
        "interaction.filter_to_grid_ms": {"p95_ms": p95, "count": search_count},
        "interaction.search_filter_ms": {"p95_ms": p95, "count": search_count},
        "grid.render_ms": {"p95_ms": p95, "count": search_count},
        "interaction.sort_ms": {"p95_ms": p95, "count": search_count},
        "data.json_parse_ms": {"p50_ms": 15, "count": 1},
    }
    return {
        "schema_version": 1, "scenario": "synthetic-viewer",
        "measured_at": stamp, "git_revision": revision, "working_tree_dirty": dirty,
        "platform": {"system": "Linux", "architecture": "aarch64"},
        "measurement": {
            "fixture": {"slide_count": slides, "text_chars": text_chars, "json_bytes": 1},
            "browser_version": browser,
            "scripted_actions": {"searches": search_count},
            "browser_report": {"timings": timing, "library": {"slides": slides}},
            "js_heap_used_mb": 20.0, "dom_nodes": 700,
        },
        "_file": title,
    }


def test_compare_percent_threshold_and_min_p95_samples():
    base = sample("111", "2026-11-01T00:00:00Z", p95=20)
    cand = sample("222", "2026-11-02T00:00:00Z", p95=28, startup=290)
    comparison = module.compare_pair(base, cand, module.DEFAULT_WARN_PCT)
    assert comparison["metrics"]["startup_ms"]["status"] == "warning"
    assert comparison["metrics"]["filter_to_grid_p95_ms"]["delta_pct"] == 40.0
    assert comparison["metrics"]["filter_to_grid_p95_ms"]["status"] == "warning"
    cand["measurement"]["browser_report"]["timings"]["interaction.filter_to_grid_ms"]["count"] = 2
    result = module.compare_pair(base, cand, module.DEFAULT_WARN_PCT)
    assert result["metrics"]["filter_to_grid_p95_ms"]["status"] == "inconclusive"
    assert result["metrics"]["filter_to_grid_p95_ms"]["delta_pct"] is None


def test_different_platform_browser_dataset_workload_or_dirty_runs_never_compare():
    base = sample("111", "2026-11-01T00:00:00Z")
    incompatible = [
        sample("222", "2026-11-02T00:00:00Z", slides=20000),
        sample("222", "2026-11-02T00:00:00Z", browser="Chrome/101"),
        sample("222", "2026-11-02T00:00:00Z", search_count=6),
        sample("222", "2026-11-02T00:00:00Z", text_chars=100),
    ]
    for candidate in incompatible:
        with pytest.raises(ValueError, match="incompatible"):
            module.compare_pair(base, candidate, module.DEFAULT_WARN_PCT)
    dirty = sample("222", "2026-11-02T00:00:00Z", dirty=True)
    with pytest.raises(ValueError, match="clean"):
        module.compare_pair(base, dirty, module.DEFAULT_WARN_PCT)
    compared = module.generate_comparisons([base, dirty], module.DEFAULT_WARN_PCT)
    assert compared["comparisons"] == []


def test_history_picks_recent_distinct_revision_and_handles_unavailable_metrics():
    records = [
        sample("111", "2026-11-01T00:00:00Z", p95=10),
        sample("111", "2026-11-01T01:00:00Z", p95=11),
        sample("222", "2026-11-02T00:00:00Z", p95=19),
    ]
    records[2]["measurement"]["js_heap_used_mb"] = None
    result = module.generate_comparisons(records, module.DEFAULT_WARN_PCT)
    assert len(result["comparisons"]) == 1
    comp = result["comparisons"][0]
    assert comp["baseline_revision"] == "111" and comp["candidate_revision"] == "222"
    assert comp["metrics"]["filter_to_grid_p95_ms"]["delta_pct"] == pytest.approx(72.73)
    assert comp["metrics"]["heap_mb"]["status"] == "unavailable"


def test_threshold_validation_and_escaped_html(tmp_path):
    thresholds = tmp_path / "limits.json"
    thresholds.write_text('{"startup_ms":100}')
    assert module.load_thresholds(thresholds)["startup_ms"] == 100
    thresholds.write_text('{"unrecognized":5}')
    with pytest.raises(ValueError, match="unrecognized"):
        module.load_thresholds(thresholds)
    thresholds.write_text('{"startup_ms":-1}')
    with pytest.raises(ValueError, match="invalid"):
        module.load_thresholds(thresholds)

    r = sample("<script>alert(1)</script>", "2026-11-01T00:00:00Z", title="../evil<script>.json")
    out = module.render_html({"comparisons": [], "exclusions": []}, [r])
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_cli_reports_warning_only_unless_explicitly_strict(tmp_path):
    root = tmp_path / "reports"
    root.mkdir()
    a = sample("111", "2026-11-01T00:00:00Z", p95=10)
    b = sample("222", "2026-11-02T00:00:00Z", p95=30)
    for name, record in (("viewer-6000-a.json", a), ("viewer-6000-b.json", b)):
        record.pop("_file")
        (root / name).write_text(json.dumps(record))
    assert module.main(["--reports-dir", str(root)]) == 0
    comparison = json.loads((root / "comparisons.json").read_text(encoding="utf-8"))
    assert comparison["comparisons"][0]["warning_count"] >= 1
    assert "Performance History" in (root / "history.html").read_text(encoding="utf-8")
    assert module.main(["--reports-dir", str(root), "--fail-on-warning"]) == 2
    assert module.main(["--reports-dir", str(tmp_path / "empty")]) == 1


def test_only_fixture_reports_are_loaded(tmp_path):
    source = tmp_path / "reports"
    source.mkdir()
    valid = sample("111", "2026-11-01T00:00:00Z")
    valid.pop("_file")
    (source / "viewer-valid.json").write_text(json.dumps(valid))
    (source / "viewer-invalid.json").write_text("{not-json")
    (source / "viewer-other.json").write_text('{"scenario":"other"}')
    found, rejected = module.load_reports(source)
    assert len(found) == 1 and len(rejected) == 1
