"""Compare local synthetic viewer benchmarks across compatible Git revisions.

Run:
  python scripts/benchmark_history.py
  python scripts/benchmark_history.py --thresholds config/performance_thresholds.example.json

The default generates .runtime/benchmarks/history.html and comparisons.json.
No network operations; output stays on this machine unless shared explicitly.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRECTORY = ROOT / ".runtime" / "benchmarks"
METRICS: dict[str, tuple[str, str]] = {
    "startup_ms": ("startup.interactive_ms", "p50_ms"),
    "filter_to_grid_p95_ms": ("interaction.filter_to_grid_ms", "p95_ms"),
    "search_p95_ms": ("interaction.search_filter_ms", "p95_ms"),
    "grid_p95_ms": ("grid.render_ms", "p95_ms"),
    "sort_p95_ms": ("interaction.sort_ms", "p95_ms"),
    "parse_ms": ("data.json_parse_ms", "p50_ms"),
    "heap_mb": ("heap", "js_heap_used_mb"),
    "dom_nodes": ("dom", "dom_nodes"),
}
DEFAULT_WARN_PCT: dict[str, float] = {
    "startup_ms": 25.0, "filter_to_grid_p95_ms": 25.0,
    "search_p95_ms": 30.0, "grid_p95_ms": 30.0,
    "sort_p95_ms": 30.0, "parse_ms": 30.0,
    "heap_mb": 25.0, "dom_nodes": 25.0,
}
MIN_P95_OBSERVATIONS = 5


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return float(value)


def extract_metric(record: dict, key: str) -> tuple[float | None, int | None]:
    measurement = record["measurement"]
    if key == "heap_mb":
        return _finite_number(measurement.get("js_heap_used_mb")), None
    if key == "dom_nodes":
        return _finite_number(measurement.get("dom_nodes")), None
    metric_name, field = METRICS[key]
    timing = measurement.get("browser_report", {}).get("timings", {}).get(metric_name, {})
    return _finite_number(timing.get(field)), timing.get("count")


def compatible_key(record: dict) -> tuple:
    measure = record["measurement"]
    fixture = measure["fixture"]
    platform = record["platform"]
    return (
        record["scenario"],
        fixture["slide_count"],
        fixture["text_chars"],
        measure["scripted_actions"].get("searches"),
        platform["system"],
        platform["architecture"],
        measure["browser_version"],
    )


def load_reports(directory: Path) -> tuple[list[dict], list[str]]:
    valid: list[dict] = []
    skipped: list[str] = []
    for path in sorted(directory.glob("viewer-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("schema_version") != 1 or data.get("scenario") != "synthetic-viewer":
                continue
            compatible_key(data)
            if not isinstance(data.get("git_revision"), str):
                raise ValueError("missing Git revision")
            datetime.fromisoformat(data["measured_at"].replace("Z", "+00:00"))
            data["_file"] = path.name
            valid.append(data)
        except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
            skipped.append(path.name + ": " + str(exc))
    valid.sort(key=lambda record: (record["measured_at"], record["_file"]))
    return valid, skipped


def load_thresholds(path: Path | None) -> dict[str, float]:
    if path is None:
        return DEFAULT_WARN_PCT.copy()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("thresholds must be an object mapping metric names to percentages")
    unknown = set(raw) - set(METRICS)
    if unknown:
        raise ValueError("unrecognized metric thresholds: " + ", ".join(sorted(unknown)))
    merged = DEFAULT_WARN_PCT.copy()
    for name, value in raw.items():
        finite = _finite_number(value)
        if finite is None or finite > 500:
            raise ValueError("invalid threshold percentage for " + name)
        merged[name] = finite
    return merged


def compare_pair(baseline: dict, candidate: dict, thresholds: dict[str, float]) -> dict:
    if compatible_key(baseline) != compatible_key(candidate):
        raise ValueError("Cannot compare incompatible benchmark environments/workloads")
    if baseline.get("working_tree_dirty") is not False or candidate.get("working_tree_dirty") is not False:
        raise ValueError("Automatic comparison requires two clean committed runs")
    metrics = {}
    for name, (_timing, field) in METRICS.items():
        before, count_before = extract_metric(baseline, name)
        after, count_after = extract_metric(candidate, name)
        status = "ok"
        delta_pct = None
        reason = None
        if before is None or after is None:
            status, reason = "unavailable", "metric not supported or missing"
        elif field == "p95_ms" and (
            not isinstance(count_before, int) or count_before < MIN_P95_OBSERVATIONS
            or not isinstance(count_after, int) or count_after < MIN_P95_OBSERVATIONS
        ):
            status, reason = "inconclusive", "p95 needs at least 5 observations in both runs"
        elif before == 0:
            status, reason = "inconclusive", "zero baseline cannot produce a percent change"
        else:
            delta_pct = round((after - before) / before * 100, 2)
            if delta_pct > thresholds[name]:
                status = "warning"
        metrics[name] = {
            "baseline": before, "candidate": after,
            "delta_pct": delta_pct, "threshold_pct": thresholds[name],
            "status": status, "reason": reason,
            "baseline_observations": count_before, "candidate_observations": count_after,
        }
    return {
        "scenario": compatible_key(candidate),
        "baseline_revision": baseline["git_revision"],
        "candidate_revision": candidate["git_revision"],
        "baseline_file": baseline["_file"],
        "candidate_file": candidate["_file"],
        "metrics": metrics,
        "warning_count": sum(item["status"] == "warning" for item in metrics.values()),
    }


def generate_comparisons(records: list[dict], thresholds: dict[str, float]) -> dict:
    groups = defaultdict(list)
    for record in records:
        groups[compatible_key(record)].append(record)
    comparisons = []
    exclusions = []
    for key in sorted(groups, key=lambda k: str(k)):
        records_group = groups[key]
        clean = [r for r in records_group if r.get("working_tree_dirty") is False]
        revisions = []
        # Keep the last run of a revision so adjacent samples are distinct code versions.
        for record in clean:
            if revisions and revisions[-1]["git_revision"] == record["git_revision"]:
                revisions[-1] = record
            else:
                revisions.append(record)
        if len(revisions) < 2:
            exclusions.append({
                "scenario": key,
                "reason": "need two comparable clean runs from different revisions",
                "reports": len(records_group),
            })
            continue
        comparisons.append(compare_pair(revisions[-2], revisions[-1], thresholds))
    return {"comparisons": comparisons, "exclusions": exclusions}


def _sparkline(entries: list[dict], metric: str) -> str:
    values = [extract_metric(entry, metric)[0] for entry in entries]
    good = [(idx, value) for idx, value in enumerate(values) if value is not None]
    if len(good) < 2:
        return "—"
    low, high = min(y for _, y in good), max(y for _, y in good)
    span = max(0.001, high - low)
    width, height = 155, 34
    points = " ".join(
        f"{8 + idx * (width - 16) / max(1, len(values)-1):.1f},"
        f"{height - 5 - (value-low) / span * (height-12):.1f}" for idx, value in good
    )
    return ('<svg width="155" height="34" viewBox="0 0 155 34" '
            'role="img" aria-label="Historical metric trend"><polyline points="'
            + points + '" fill="none" stroke="#245d9d" stroke-width="2"/></svg>')


def render_html(result: dict, records: list[dict]) -> str:
    escape = html.escape
    comparisons = result["comparisons"]
    warnings = sum(c["warning_count"] for c in comparisons)
    rows = []
    groups = defaultdict(list)
    for record in records:
        groups[compatible_key(record)].append(record)
    for comparison in comparisons:
        key = tuple(comparison["scenario"])
        scenario = key[1]
        for name, measured in comparison["metrics"].items():
            delta = measured["delta_pct"]
            delta_label = "—" if delta is None else f"{delta:+.1f}%"
            status = measured["status"]
            status_text = status if not measured["reason"] else status + " (" + measured["reason"] + ")"
            rows.append(
                "<tr><td>" + escape(str(scenario)) + "</td><td>" + escape(name.replace("_", " ")) + "</td>"
                "<td>" + escape(comparison["baseline_revision"]) + "</td>"
                "<td>" + escape(comparison["candidate_revision"]) + "</td>"
                "<td class=num>" + escape(str(measured["baseline"])) + "</td>"
                "<td class=num>" + escape(str(measured["candidate"])) + "</td>"
                "<td class=num>" + escape(delta_label) + "</td>"
                '<td class="' + escape(status) + '">' + escape(status_text) + "</td>"
                "<td>" + _sparkline(groups[key], name) + "</td></tr>"
            )
    history = []
    for record in records:
        slide_count = record["measurement"]["fixture"]["slide_count"]
        stamp = record["measured_at"].replace("T", " ")[:19]
        history.append(
            "<tr><td>" + escape(stamp) + "</td><td>" + escape(record["git_revision"]) + "</td>"
            "<td>" + str(slide_count) + "</td><td>" + escape(record["platform"]["system"]) + "/"
            + escape(record["platform"]["architecture"]) + "</td><td>"
            + escape(record["measurement"]["browser_version"]) + "</td><td>"
            + ("clean" if record.get("working_tree_dirty") is False else "unverified/dirty")
            + "</td><td>" + escape(record["_file"]) + "</td></tr>"
        )
    exclusions = "".join(
        "<li>" + escape(str(e["scenario"][1])) + " slides — " + escape(e["reason"]) + "</li>"
        for e in result["exclusions"]
    )
    return """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>PowerPoint Viewer Performance History</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{max-width:1260px;margin:35px auto;padding:0 22px;font:14px/1.5 system-ui,sans-serif;color:#18263a}
h1{font-size:24px}h2{font-size:17px;margin-top:30px}table{width:100%;border-collapse:collapse;font-size:12px}
th,td{padding:9px 7px;border-bottom:1px solid #d9e2eb;text-align:left;vertical-align:middle}
th{background:#f4f6f9;position:sticky;top:0}.num{font-variant-numeric:tabular-nums;text-align:right}
.warning{font-weight:700;color:#a34414}.inconclusive,.unavailable{color:#677489}
.ok{color:#225c40}.note{color:#58657c}.scroll{overflow:auto}
</style></head><body>
<h1>PowerPoint Viewer — Performance History</h1>
<p class=note>Local synthetic benchmarks. Comparisons only between clean revisions on the same OS, architecture, browser build, slide count, text length, and search workload. This does not validate real images or PowerPoint rendering.</p>
<p><strong>""" + str(len(records)) + " reports · " + str(len(comparisons)) + " comparable scenarios · " + str(warnings) + """ warning metrics</strong></p>
<h2>Latest comparable revisions</h2><div class=scroll><table><thead><tr>
<th>Slides</th><th>Metric</th><th>Baseline</th><th>Candidate</th><th>Before</th><th>After</th><th>Change</th><th>Assessment</th><th>Trend</th>
</tr></thead><tbody>""" + "".join(rows) + """</tbody></table></div>
<h2>Unmatched groups</h2><ul>""" + (exclusions or "<li>None</li>") + """</ul>
<h2>Saved runs</h2><div class=scroll><table><thead><tr><th>UTC</th><th>Revision</th><th>Slides</th><th>Platform</th><th>Browser</th><th>Source state</th><th>Local report</th></tr></thead><tbody>""" + "".join(history) + """</tbody></table></div>
<p class=note>Warning thresholds are relative percentages. p95 alerts require at least five observations in both runs; incomplete or unsupported metrics are inconclusive. Generated offline, with no network or automatic upload.</p>
</body></html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--html", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--thresholds", type=Path)
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args(argv)
    try:
        records, skipped = load_reports(args.reports_dir)
        if not records:
            raise ValueError("no valid synthetic benchmark runs in " + str(args.reports_dir))
        thresholds = load_thresholds(args.thresholds)
        comparison = generate_comparisons(records, thresholds)
        result = {
            "schema_version": 1,
            "generated_at": datetime.now().astimezone().isoformat(),
            "report_count": len(records),
            "thresholds": thresholds,
            "skipped_reports": skipped,
            **comparison,
        }
        target_html = args.html or args.reports_dir / "history.html"
        target_json = args.json or args.reports_dir / "comparisons.json"
        target_html.parent.mkdir(parents=True, exist_ok=True)
        target_json.parent.mkdir(parents=True, exist_ok=True)
        target_html.write_text(render_html(result, records), encoding="utf-8")
        target_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        warnings = sum(pair["warning_count"] for pair in result["comparisons"])
        print(f"{len(records)} runs, {len(result['comparisons'])} comparable scenarios, {warnings} warnings")
        print(f"HTML: {target_html} \nJSON: {target_json}")
        if skipped:
            print("Skipped invalid files: " + ", ".join(skipped), file=sys.stderr)
        return 2 if warnings and args.fail_on_warning else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("Performance report error: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
