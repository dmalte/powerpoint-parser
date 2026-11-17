"""M008h: bounded, path-free conversion-failure diagnostics."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/classify_conversion_failures.py"


def _module():
    spec = importlib.util.spec_from_file_location("classify_conversion_failures", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _line(index, total, file, reason):
    return f"2026-11-16 16:18:00  ERROR    [{index}/{total}] Failed: {file} — {reason}\n"


def test_classifies_latest_scan_without_exposing_sensitive_details(tmp_path):
    log = tmp_path / "agent.log"
    secret = "auth_token=sensitive-example-value"
    log.write_text(
        "2026-11-16 15:00:00  INFO Processing 3 files...\n"
        + _line(1, 3, "very-secret-previous.pdf", "password protected")
        + "2026-11-16 16:18:00  INFO Processing 7 files...\n"
        + _line(1, 7, "/private/Documents/tax secret.pdf", "Document requires a password " + secret)
        + _line(2, 7, "C:/private/folder/PowerPoint Account.pptx", "PowerPoint PDF export -9074 " + secret)
        + _line(3, 7, "hidden profile.pptx", "Permission denied " + secret)
        + _line(4, 7, "another.pdf", "invalid xref table")
        + _line(5, 7, "file5.pdf", "unexpected error " + secret)
        + _line(6, 7, "outdated.txt", "bad")
        + "2026-11-16 16:18:01  INFO [7/7] Processed: normal.pdf (1 pages)\n",
        encoding="utf-8",
    )
    report = _module().summarize_latest_scan(log)
    assert report["schema_version"] == 1
    assert report["scan_window_found"] is True
    assert report["expected_candidates"] == 7
    assert report["failed_attempts"] == 5
    assert report["by_format"] == {"pdf": 3, "pptx": 2}
    assert {(r["format"], r["category"]): r["count"] for r in report["categories"]} == {
        ("pdf", "password_or_encrypted"): 1,
        ("pptx", "powerpoint_automation"): 1,
        ("pptx", "permission_or_access"): 1,
        ("pdf", "invalid_or_unreadable"): 1,
        ("pdf", "unclassified"): 1,
    }
    output = json.dumps(report)
    for forbidden in ("very-secret", "tax secret", "Account", "auth_token", secret, "private", "-9074", "/", "\\\\"):
        assert forbidden not in output
    assert report["retry_policy_applied"] is False
    assert set(c["retry_recommendation"] for c in report["categories"]) <= {
        "after_decryption_source_change_or_explicit_retry",
        "after_permission_restored_or_explicit_retry",
        "bounded_retry_after_interactive_session_check",
        "after_source_repair_or_explicit_retry",
        "bounded_retry_after_environment_check",
        "inspect_local_log_before_retry",
    }


def test_newer_noop_scan_discards_previous_errors(tmp_path):
    log = tmp_path / "agent.log"
    log.write_text(
        "Processing 2 files...\n" + _line(1, 2, "bad.pdf", "password")
        + "No new or changed files to process\n",
    )
    report = _module().summarize_latest_scan(log)
    assert report["expected_candidates"] == 0
    assert report["failed_attempts"] == 0
    assert report["categories"] == []


def test_retries_skipped_by_new_policy_are_not_reported_as_recent_failures(tmp_path):
    log = tmp_path / "agent.log"
    log.write_text(
        "Processing 1 files...\n" + _line(1, 1, "locked.pdf", "encrypted")
        + "No eligible files to process; 1 encrypted holds, 0 transient backoffs\n"
    )
    report = _module().summarize_latest_scan(log)
    assert report["scan_window_found"] is True
    assert report["expected_candidates"] == 0
    assert report["failed_attempts"] == 0


def test_missing_log_and_no_scan_marker_do_not_infer_results(tmp_path):
    missing = _module().summarize_latest_scan(tmp_path / "unseen.log")
    assert not missing["scan_window_found"]
    assert missing["expected_candidates"] is None
    (tmp_path / "unseen.log").write_text(_line(3, 5, "secret.pdf", "encrypted"))
    unknown = _module().summarize_latest_scan(tmp_path / "unseen.log")
    assert not unknown["scan_window_found"]
    assert unknown["failed_attempts"] == 0


def test_tail_truncation_is_reported_and_latest_scan_is_still_detected(tmp_path):
    log = tmp_path / "agent.log"
    log.write_text(
        "old path " + ("x" * 1500) + "\n"
        + "Processing 98 files...\n"
        + _line(1, 98, "one.pdf", "encrypted")
        + _line(2, 98, "two.pptx", "PowerPoint -9074")
    )
    report = _module().summarize_latest_scan(log, max_bytes=90)
    assert report["scan_window_truncated_at_file_start"] is True
    # The last scan header fell outside the bounded tail. Do not make a false
    # completeness or failure-count claim from unanchored error rows.
    assert not report["scan_window_found"]
    assert report["failed_attempts"] == 0


def test_latest_scan_marker_within_bounded_tail(tmp_path):
    log = tmp_path / "agent.log"
    log.write_text("old path " + ("q" * 1300) + "\n"
                   + "Processing 3 files...\n" + _line(2, 3, "one.pdf", "encrypted"))
    report = _module().summarize_latest_scan(log, max_bytes=120)
    assert report["scan_window_truncated_at_file_start"] is True
    assert report["scan_window_found"] is True
    assert report["failed_attempts"] == 1


def test_cli_writes_only_path_free_json_and_does_not_modify_log(tmp_path):
    log = tmp_path / "private-agent.log"
    log.write_text("Processing 2 files...\n" + _line(1, 2, "private.pdf", "encrypted"))
    before = log.read_bytes()
    output = tmp_path / "reports/recent.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--log", str(log), "--output", str(output)],
        text=True, capture_output=True, timeout=10, cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert json.loads(result.stdout) == report
    assert "private.pdf" not in result.stdout
    assert str(log) not in result.stdout
    assert log.read_bytes() == before
    assert report["failed_attempts"] == 1


def test_fixed_error_classifier_priority():
    classify = _module().classify_failure
    assert classify("pdf", "Cannot authenticate or password required") == "password_or_encrypted"
    assert classify("pptx", "PowerPoint PDF export failed with -9074") == "powerpoint_automation"
    assert classify("pptx", "Permission denied from PowerPoint") == "permission_or_access"
    assert classify("pptx", "AppleScript command timed out") == "timeout"
    assert classify("pdf", "Invalid PDF xref") == "invalid_or_unreadable"
    assert classify("md", "Unknown internal processor condition") == "unclassified"
