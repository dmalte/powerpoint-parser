#!/usr/bin/env python3
"""Summarize the latest local agent scan's conversion failures without paths.

Consumes only a bounded tail of agent.log, writes no user file details, and
never changes the current scan/retry schedule. Recommendations are advisory.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from ppt_visual_archive.platform_paths import default_log_dir
from ppt_visual_archive.failure_classification import classify_failure

MAX_LOG_SCAN_BYTES = 4 * 1024 * 1024
_SCAN_START = re.compile(r"\bProcessing (\d+) files\.\.\.")
_NO_CHANGES = "No new or changed files to process"
_NO_ELIGIBLE = "No eligible files to process;"
_FAILURE = re.compile(r"\[(\d+)/(\d+)\]\s+(?:Markdown failed|Failed):\s+(.+?\.(?:pptx|pdf|md))\s+—\s+(.+)$", re.IGNORECASE)

# Names and advice are deliberately fixed constants. Never echo the raw log
# reason, filename, path, or arbitrary exception text into the report.
_RETRY = {
    "password_or_encrypted": "after_decryption_source_change_or_explicit_retry",
    "permission_or_access": "after_permission_restored_or_explicit_retry",
    "powerpoint_automation": "bounded_retry_after_interactive_session_check",
    "invalid_or_unreadable": "after_source_repair_or_explicit_retry",
    "timeout": "bounded_retry_after_environment_check",
    "unclassified": "inspect_local_log_before_retry",
}



def _tail(path: Path, max_bytes: int = MAX_LOG_SCAN_BYTES) -> tuple[list[str], bool]:
    if not path.is_file():
        return [], False
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        truncated = size > max_bytes
        stream.seek(max(0, size - max_bytes))
        if truncated:
            # Ignore one partial line from a tail offset in the middle of a
            # sensitive filename or exception; do not publish raw bytes.
            stream.readline()
        return stream.read().decode("utf-8", "replace").splitlines(), truncated


def summarize_latest_scan(path: str | Path, *, max_bytes: int = MAX_LOG_SCAN_BYTES) -> dict:
    """Return path-free counts for the most recent scan window in the log."""
    try:
        lines, truncated = _tail(Path(path), max_bytes)
    except OSError:
        lines, truncated = [], False
    marker_index = None
    expected = None
    for index, line in enumerate(lines):
        match = _SCAN_START.search(line)
        if match:
            marker_index = index
            expected = int(match.group(1))
        elif _NO_CHANGES in line or _NO_ELIGIBLE in line:
            marker_index = index
            expected = 0

    counts: Counter[tuple[str, str]] = Counter()
    if marker_index is not None and expected:
        for line in lines[marker_index + 1:]:
            matched = _FAILURE.search(line)
            if matched is None:
                continue
            extension = matched.group(3).rsplit(".", 1)[-1].lower()
            category = classify_failure(extension, matched.group(4))
            counts[(extension, category)] += 1

    categories = [
        {"format": extension, "category": category, "count": count,
         "retry_recommendation": _RETRY[category]}
        for (extension, category), count in sorted(counts.items())
    ]
    return {
        "schema_version": 1,
        "kind": "local_conversion_failure_summary",
        "scan_window_found": marker_index is not None,
        "scan_window_truncated_at_file_start": truncated,
        "expected_candidates": expected,
        "failed_attempts": sum(counts.values()),
        "by_format": dict(sorted(Counter({
            kind: sum(count for (ext, _), count in counts.items() if ext == kind)
            for kind in ("pdf", "pptx", "md") if any(ext == kind for ext, _ in counts)
        }).items())),
        "categories": categories,
        "retry_policy_applied": False,
        "note": "Advisory classification only; the installed scanner continues its existing retry schedule.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=default_log_dir() / "agent.log")
    parser.add_argument("--output", type=Path, help="Optional local path for a path-free JSON report")
    args = parser.parse_args(argv)
    report = summarize_latest_scan(args.log)
    contents = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(contents, encoding="utf-8")
    print(contents, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
