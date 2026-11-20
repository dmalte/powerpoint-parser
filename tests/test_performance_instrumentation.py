"""Local-only performance diagnostics: scanner, builder, browser and server."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import urllib.request
from pathlib import Path

import pytest

from ppt_visual_archive import perf_metrics
from ppt_visual_archive.builder import build_viewer
from ppt_visual_archive.config import default_config
from ppt_visual_archive.perf_metrics import TimedRun, recent_runs
from ppt_visual_archive.pipeline import run_scan
from ppt_visual_archive.server import create_server


ROOT = Path(__file__).resolve().parents[1]


def test_timed_run_aggregates_stages_and_writes_no_paths(tmp_path):
    run = TimedRun("scan")
    with run.step("filesystem_scan"):
        pass
    with run.step("filesystem_scan"):
        pass
    run.count("discovered_files", 17)
    payload = run.finish(log_dir=tmp_path)
    assert payload["durations_ms"]["filesystem_scan"] >= 0
    assert payload["counts"]["discovered_files"] == 17
    assert [entry["operation"] for entry in recent_runs(log_dir=tmp_path)] == ["scan"]
    assert not any(key in payload for key in ("root", "file_path", "scan_path", "documents"))


def test_scan_and_build_produce_aggregate_log_without_source_names(tmp_path, monkeypatch):
    source = tmp_path / "PRIVATE_PRESENTATIONS_FOLDER"
    source.mkdir()
    output = tmp_path / "viewer"
    config = default_config(str(output), [str(source)])
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")

    # A no-change incremental scan must be measured as well.
    scan_result = run_scan(config)
    build_viewer(config)
    assert scan_result["processed_ok"] == 0

    events = recent_runs(log_dir=tmp_path / "logs")
    assert [entry["operation"] for entry in events] == ["scan", "build"]
    assert events[0]["counts"]["discovered_files"] == 0
    assert "filesystem_scan" in events[0]["durations_ms"]
    assert "change_detection" in events[0]["durations_ms"]
    assert "total" in events[0]["durations_ms"]
    assert "json_write" in events[1]["durations_ms"]
    assert "html_render_write" in events[1]["durations_ms"]
    assert events[1]["counts"]["slides"] == 0

    log_text = (tmp_path / "logs" / "performance.jsonl").read_text(encoding="utf-8")
    assert "PRIVATE_PRESENTATIONS_FOLDER" not in log_text
    assert str(tmp_path) not in log_text

    html = (output / "index.html").read_text(encoding="utf-8")
    assert 'id="perf-toggle"' in html
    assert 'id="perf-download"' in html
    assert "js/performance.js" in html
    assert (output / "js" / "performance.js").is_file()


def test_pdf_render_time_and_file_counts_are_measured(tmp_path, monkeypatch):
    import fitz

    source = tmp_path / "private_pdfs"
    source.mkdir()
    pdf = fitz.open()
    pdf.new_page(width=300, height=200)
    pdf.save(source / "PrivateArchiveDocument.pdf")
    pdf.close()
    config = default_config(str(tmp_path / "out"), [str(source)])
    config.file_types = ["pdf"]
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: tmp_path / "logs")

    summary = run_scan(config)
    event = recent_runs(log_dir=tmp_path / "logs")[-1]
    assert summary["processed_ok"] == 1
    assert event["counts"]["pdf_files_to_process"] == 1
    assert event["counts"]["processed_slides"] == 1
    assert event["durations_ms"]["pdf_render_extract"] >= 0
    assert event["durations_ms"]["sqlite_upsert"] >= 0
    assert "PrivateArchiveDocument" not in (tmp_path / "logs" / "performance.jsonl").read_text(encoding="utf-8")


def test_local_performance_api_returns_bounded_safe_events(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(perf_metrics, "default_log_dir", lambda: log_dir)
    run = TimedRun("build")
    with run.step("total"):
        pass
    run.count("slides", 6000)
    run.finish(log_dir=log_dir)

    output = tmp_path / "archive"
    output.mkdir()
    (output / "index.html").write_text("ok", encoding="utf-8")
    server = create_server(str(output), 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/api/performance", timeout=2
        ) as response:
            body = json.load(response)
            assert response.headers["Cache-Control"] == "no-store"
        assert len(body["runs"]) == 1
        assert body["runs"][0]["counts"]["slides"] == 6000
        assert "total" in body["runs"][0]["durations_ms"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_browser_hooks_are_present_and_js_is_valid():
    script = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    helper = (ROOT / "web" / "static" / "js" / "performance.js").read_text(encoding="utf-8")
    for marker in (
        'data.fetch_headers_ms', 'data.body_read_ms', 'data.json_parse_ms',
        'data.normalize_ms', 'startup.interactive_ms', 'interaction.search_filter_ms',
        'interaction.sort_ms', 'grid.render_ms', 'modal.open_ms', 'image.thumbnail_ms',
        'image.preview_ms',
    ):
        assert marker in script
    for marker in ('scroll.frame_gap_ms', 'main_thread.longtask_ms', 'Download JSON report'):
        assert marker in helper or marker in (ROOT / "web" / "templates" / "index.html.j2").read_text(encoding="utf-8")
    assert '"/api/performance"' in helper
    assert "localStorage" not in helper
    assert "sendBeacon" not in helper

    if not shutil.which("node"):
        pytest.skip("Node is not installed; static hook checks still ran")
    for name in ("app.js", "performance.js"):
        subprocess.run(
            ["node", "--check", str(ROOT / "web" / "static" / "js" / name)],
            capture_output=True,
            text=True,
            check=True,
        )


def test_browser_performance_aggregator_with_node():
    if not shutil.which("node"):
        pytest.skip("Node is not available")
    source = ROOT / "web" / "static" / "js" / "performance.js"
    harness = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const context = {
  window: {}, document: { addEventListener() {} },
  performance: { now: () => 100, getEntriesByType: () => [] },
  navigator: { userAgent: 'unit-test' },
  console,
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const api = context.window.PPTViewerPerf;
api.setLibrary(200, 6000);
api.record('interaction.search_filter_ms', 30);
api.record('interaction.search_filter_ms', 70);
api.count('image.thumbnail_errors');
const report = api.report();
if (report.library.slides !== 6000 ||
    report.timings['interaction.search_filter_ms'].p95_ms !== 70 ||
    report.timings['interaction.search_filter_ms'].count !== 2 ||
    report.counters['image.thumbnail_errors'] !== 1) {
  throw new Error('Incorrect diagnostics report: ' + JSON.stringify(report));
}
"""
    subprocess.run(["node", "-e", harness, str(source)], capture_output=True, text=True, check=True)
