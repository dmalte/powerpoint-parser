#!/usr/bin/env python3
"""Create a minimal agent-managed feature record from specs/000-template-feature."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "PROJECT_WORKFLOW.json"
TEMPLATE = ROOT / "specs" / "000-template-feature"
HANDOFF = ROOT / "dev" / "HANDOFF.md"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQ_RE = re.compile(r"^REQ-[A-Z0-9]+(?:-[A-Z0-9]+)+$")
MILESTONE_RE = re.compile(r"^M\d{3,}$")


class FeatureError(RuntimeError):
    pass


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FeatureError(f"Missing required file: {path}") from exc


def next_feature_number(specs_dir: Path) -> int:
    numbers: list[int] = []
    for path in specs_dir.iterdir():
        if not path.is_dir():
            continue
        match = re.match(r"^(\d{3})-", path.name)
        if match and match.group(1) != "000":
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def validate_references(milestone: str, requirements: list[str]) -> None:
    if not MILESTONE_RE.fullmatch(milestone):
        raise FeatureError("Milestone must look like M001 or M010.")

    invalid = [value for value in requirements if not REQ_RE.fullmatch(value)]
    if invalid:
        raise FeatureError("Invalid requirement IDs: " + ", ".join(invalid))

    roadmap = read_text(ROOT / "ROADMAP.md")
    if milestone not in roadmap:
        raise FeatureError(f"Milestone {milestone} was not found in ROADMAP.md.")

    master = read_text(ROOT / "spec" / "REQUIREMENTS.md")
    missing = [value for value in requirements if value not in master]
    if missing:
        raise FeatureError(
            "Requirement IDs were not found in spec/REQUIREMENTS.md: "
            + ", ".join(missing)
        )


def render_templates(destination: Path, replacements: dict[str, str]) -> None:
    for name in ("spec.md", "plan.md", "tasks.md"):
        source = TEMPLATE / name
        text = read_text(source)
        for token, value in replacements.items():
            text = text.replace("{{" + token + "}}", value)
        (destination / name).write_text(text, encoding="utf-8", newline="\n")


def set_active_feature(relative_path: str) -> None:
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FeatureError(f"Missing {CONFIG}") from exc
    except json.JSONDecodeError as exc:
        raise FeatureError(f"Invalid JSON in {CONFIG}: {exc}") from exc

    if not isinstance(config, dict):
        raise FeatureError("PROJECT_WORKFLOW.json must contain a JSON object.")

    config["active_feature"] = relative_path
    CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def initialize_handoff(
    *,
    relative_path: str,
    title: str,
    milestone: str,
    requirements: list[str],
) -> None:
    HANDOFF.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    requirement_text = ", ".join(requirements)
    content = (
        f"# Handoff\n\n"
        f"- Last Updated: {timestamp}\n"
        f"- Active Feature: `{relative_path}`\n\n"
        f"## Current Objective\n\n"
        f"Refine and implement **{title}** for milestone {milestone}.\n\n"
        f"## Completed\n\n"
        f"- Created the agent-managed feature record.\n"
        f"- Selected the feature in `PROJECT_WORKFLOW.json`.\n\n"
        f"## Decisions\n\n"
        f"- Workflow: agent-managed.\n"
        f"- Requirements: {requirement_text}.\n"
        f"- `spec.md`, `plan.md`, and `tasks.md` are living working documents.\n\n"
        f"## Files Changed\n\n"
        f"- `{relative_path}/spec.md`\n"
        f"- `{relative_path}/plan.md`\n"
        f"- `{relative_path}/tasks.md`\n"
        f"- `PROJECT_WORKFLOW.json`\n"
        f"- `dev/HANDOFF.md`\n\n"
        f"## Open Issues\n\n"
        f"- The generated feature documents still require project-specific refinement.\n"
        f"- `ROADMAP.md` must link to `{relative_path}` before the agent-managed feature gate passes.\n\n"
        f"## Next Step\n\n"
        f"Refine the feature specification, implementation plan, and tasks; link the "
        f"feature from the roadmap; then run the agent-managed feature pre-implementation gate.\n\n"
        f"## Validation\n\n"
        f"- No implementation validation has run yet.\n"
    )
    HANDOFF.write_text(content, encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug", help="Short kebab-case name, e.g. project-ideas")
    parser.add_argument("--title", required=True)
    parser.add_argument("--milestone", required=True)
    parser.add_argument("--requirements", nargs="+", required=True)
    parser.add_argument("--number", type=int)
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Create the feature without changing active_feature or HANDOFF.md.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if not SLUG_RE.fullmatch(args.slug):
            raise FeatureError("Slug must be lowercase kebab-case.")
        if not args.title.strip():
            raise FeatureError("Title must not be empty.")
        if args.number is not None and args.number <= 0:
            raise FeatureError("Feature number must be greater than zero.")

        validate_references(args.milestone, args.requirements)

        number = args.number or next_feature_number(ROOT / "specs")
        relative = f"specs/{number:03d}-{args.slug}"
        destination = ROOT / relative
        if destination.exists():
            raise FeatureError(f"Feature directory already exists: {relative}")

        destination.mkdir(parents=True)
        render_templates(
            destination,
            {
                "FEATURE_TITLE": args.title.strip(),
                "FEATURE_PATH": relative,
                "MILESTONE_ID": args.milestone,
                "REQUIREMENT_IDS": ", ".join(args.requirements),
            },
        )

        if not args.no_activate:
            set_active_feature(relative)
            initialize_handoff(
                relative_path=relative,
                title=args.title.strip(),
                milestone=args.milestone,
                requirements=args.requirements,
            )

    except FeatureError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Created {relative}")
    if args.no_activate:
        print("active_feature and HANDOFF.md were not changed.")
    else:
        print(f"Set active_feature to {relative}")
        print("Initialized dev/HANDOFF.md for the selected feature.")
    print(
        "Next: link the feature path in ROADMAP.md, then refine the living "
        "spec.md, plan.md, and tasks.md."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
