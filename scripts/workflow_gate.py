#!/usr/bin/env python3
"""Validate repository workflow prerequisites.

Agent-managed work uses repository-maintained ``spec.md``, ``plan.md``, and ``tasks.md``
files but does not require Spec Kit or a ``.specify`` directory.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_NAME = "PROJECT_WORKFLOW.json"

WORKFLOW_MODES = {"direct", "agent-managed", "hybrid-gated", "strict"}
CHANGE_CLASSES = {"direct", "feature", "short", "full"}
ALLOWED_CHANGE_CLASSES = {
    "direct": {"direct", "feature"},
    "agent-managed": {"direct", "feature"},
    "hybrid-gated": {"direct", "short", "full"},
    "strict": {"short", "full"},
}

REQUIREMENT_ID_RE = re.compile(r"\bREQ-[A-Z0-9]+(?:-[A-Z0-9]+)+\b")
MILESTONE_ID_RE = re.compile(r"\bM\d{3,}\b")
CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[(?P<state>[ xX])\]\s+", re.MULTILINE)


class GateError(RuntimeError):
    """Raised when a workflow prerequisite is not satisfied."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GateError(f"Missing configuration file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GateError(
            f"Invalid JSON in {path}: line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise GateError(f"Could not read {path}: {exc}") from exc


def load_config(root: Path) -> dict[str, Any]:
    value = load_json(root / CONFIG_NAME)
    if not isinstance(value, dict):
        raise GateError(f"{CONFIG_NAME} must contain a JSON object.")
    return value


def validate_config(config: dict[str, Any]) -> str:
    mode = config.get("workflow_mode")
    if mode not in WORKFLOW_MODES:
        choices = ", ".join(sorted(WORKFLOW_MODES))
        raise GateError(
            f"Unsupported workflow_mode {mode!r}. Expected one of: {choices}."
        )

    spec_kit = config.get("spec_kit", {})
    if spec_kit is not None and not isinstance(spec_kit, dict):
        raise GateError("spec_kit must be a JSON object when present.")

    return str(mode)


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def normalize_feature_path(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def feature_from_specify_state(root: Path) -> Path | None:
    state_path = root / ".specify" / "feature.json"
    if not state_path.is_file():
        return None

    try:
        state = load_json(state_path)
    except GateError:
        return None

    if not isinstance(state, dict):
        return None

    for key in ("feature_dir", "feature_path", "path", "feature"):
        value = state.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_feature_path(root, value.strip())

    return None


def unfinished_features(root: Path) -> list[Path]:
    specs_dir = root / "specs"
    if not specs_dir.is_dir():
        return []

    candidates: list[Path] = []
    for path in sorted(specs_dir.iterdir()):
        if not path.is_dir() or path.name.startswith("000-"):
            continue
        if (path / ".completed").exists():
            continue
        if any((path / name).exists() for name in ("spec.md", "plan.md", "tasks.md")):
            candidates.append(path.resolve())
    return candidates


def resolve_feature(
    root: Path,
    config: dict[str, Any],
    explicit_feature: str | Path | None = None,
) -> Path:
    if explicit_feature:
        return normalize_feature_path(root, explicit_feature)

    configured = config.get("active_feature")
    if isinstance(configured, str) and configured.strip():
        return normalize_feature_path(root, configured.strip())

    env_value = os.environ.get("SPECIFY_FEATURE_DIRECTORY")
    if env_value and env_value.strip():
        return normalize_feature_path(root, env_value.strip())

    specify_feature = feature_from_specify_state(root)
    if specify_feature is not None:
        return specify_feature

    candidates = unfinished_features(root)
    if len(candidates) == 1:
        return candidates[0]

    if not candidates:
        raise GateError(
            "Could not resolve an active feature. Configure active_feature in "
            f"{CONFIG_NAME} or pass --feature."
        )

    rendered = ", ".join(display_path(path, root) for path in candidates)
    raise GateError(
        "Multiple unfinished feature directories exist and no active feature is "
        f"selected: {rendered}. Configure active_feature or pass --feature."
    )


def ensure_feature_is_under_specs(root: Path, feature: Path) -> None:
    specs_root = (root / "specs").resolve()
    try:
        feature.resolve().relative_to(specs_root)
    except ValueError as exc:
        raise GateError(
            f"Feature path must be inside {display_path(specs_root, root)}: "
            f"{display_path(feature, root)}"
        ) from exc


def read_required_artifacts(root: Path, feature: Path) -> dict[str, str]:
    ensure_feature_is_under_specs(root, feature)

    if not feature.is_dir():
        raise GateError(
            f"Feature directory does not exist: {display_path(feature, root)}"
        )

    contents: dict[str, str] = {}
    missing: list[str] = []
    empty: list[str] = []

    for name in ("spec.md", "plan.md", "tasks.md"):
        path = feature / name
        if not path.is_file():
            missing.append(display_path(path, root))
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise GateError(f"Could not read {display_path(path, root)}: {exc}") from exc

        if not text.strip():
            empty.append(display_path(path, root))
        contents[name] = text

    if missing:
        raise GateError("Missing required feature artifacts: " + ", ".join(missing))
    if empty:
        raise GateError("Empty required feature artifacts: " + ", ".join(empty))

    return contents


def validate_agent_managed_feature(root: Path, feature: Path) -> list[str]:
    contents = read_required_artifacts(root, feature)
    combined = "\n".join(contents.values())

    task_matches = list(CHECKBOX_RE.finditer(contents["tasks.md"]))
    if not task_matches:
        raise GateError(
            f"{display_path(feature / 'tasks.md', root)} must contain at least "
            "one Markdown checkbox task."
        )

    requirement_ids = sorted(set(REQUIREMENT_ID_RE.findall(combined)))
    if not requirement_ids:
        raise GateError(
            "Agent-managed feature artifacts must reference at least one requirement ID "
            "such as REQ-AREA-001."
        )

    requirements_path = root / "spec" / "REQUIREMENTS.md"
    if not requirements_path.is_file():
        raise GateError(
            f"Missing master requirements file: {display_path(requirements_path, root)}"
        )
    requirements_text = requirements_path.read_text(encoding="utf-8")
    master_requirement_ids = set(REQUIREMENT_ID_RE.findall(requirements_text))
    unknown_requirements = sorted(set(requirement_ids) - master_requirement_ids)
    if unknown_requirements:
        raise GateError(
            "Feature references requirement IDs not found in "
            f"{display_path(requirements_path, root)}: "
            + ", ".join(unknown_requirements)
        )

    milestone_ids = sorted(set(MILESTONE_ID_RE.findall(combined)))
    if not milestone_ids:
        raise GateError(
            "Agent-managed feature artifacts must identify at least one roadmap milestone "
            "such as M010."
        )

    roadmap_path = root / "ROADMAP.md"
    if not roadmap_path.is_file():
        raise GateError(f"Missing roadmap file: {display_path(roadmap_path, root)}")
    roadmap_text = roadmap_path.read_text(encoding="utf-8")

    unknown_milestones = [
        milestone for milestone in milestone_ids if milestone not in roadmap_text
    ]
    if unknown_milestones:
        raise GateError(
            "Feature references milestone IDs not found in "
            f"{display_path(roadmap_path, root)}: "
            + ", ".join(unknown_milestones)
        )

    feature_relative = feature.resolve().relative_to(root.resolve()).as_posix()
    if feature_relative not in roadmap_text and feature.name not in roadmap_text:
        raise GateError(
            f"{display_path(roadmap_path, root)} must reference the selected "
            f"feature path {feature_relative}."
        )

    completed = sum(
        1 for match in task_matches if match.group("state").lower() == "x"
    )
    total = len(task_matches)

    return [
        "Agent-managed feature gate passed.",
        f"Feature: {display_path(feature, root)}",
        "Required artifacts: spec.md PASS, plan.md PASS, tasks.md PASS",
        f"Roadmap reference: PASS ({', '.join(milestone_ids)})",
        f"Requirement references: PASS ({', '.join(requirement_ids)})",
        f"Task checklist present: PASS ({completed}/{total} completed)",
        "Spec Kit is not required for this agent-managed workflow.",
    ]


def spec_kit_enabled(config: dict[str, Any]) -> bool:
    value = config.get("spec_kit", {})
    return isinstance(value, dict) and value.get("enabled") is True


def pre_implement(
    config: dict[str, Any],
    change_class: str,
    *,
    root: Path = DEFAULT_ROOT,
    explicit_feature: str | Path | None = None,
) -> list[str]:
    mode = validate_config(config)

    if change_class not in CHANGE_CLASSES:
        choices = ", ".join(sorted(CHANGE_CLASSES))
        raise GateError(
            f"Unsupported change class {change_class!r}. Expected one of: {choices}."
        )

    if change_class not in ALLOWED_CHANGE_CLASSES[mode]:
        allowed = ", ".join(sorted(ALLOWED_CHANGE_CLASSES[mode]))
        raise GateError(
            f"Workflow mode {mode!r} does not permit change class "
            f"{change_class!r}. Allowed: {allowed}."
        )

    if change_class == "direct":
        return [
            "Direct path allowed.",
            "Validate the change using the configured project commands.",
        ]

    feature = resolve_feature(root, config, explicit_feature)

    if change_class == "feature":
        return validate_agent_managed_feature(root, feature)

    if not spec_kit_enabled(config):
        raise GateError(
            f"{change_class} work requires Spec Kit, but spec_kit.enabled is false."
        )

    specify_dir = root / ".specify"
    if not specify_dir.is_dir():
        raise GateError(
            "Spec Kit is enabled but .specify/ is missing. Initialize the project."
        )

    read_required_artifacts(root, feature)

    lines = [
        f"Minimum {change_class} prerequisites found in "
        f"{display_path(feature, root)}."
    ]
    if change_class == "full":
        lines.append(
            "Reminder: complete the configured clarify/checklist/analyze gates "
            "before implementation. This script validates files, not chat history."
        )
    return lines


def unresolved_commands(config: dict[str, Any]) -> list[str]:
    commands = config.get("commands")
    if not isinstance(commands, dict):
        return ["commands"]

    required = ("setup", "run", "fast_check", "test", "full_check")
    return [
        key
        for key in required
        if not isinstance(commands.get(key), str) or not commands[key].strip()
    ]


def status(config: dict[str, Any], *, root: Path = DEFAULT_ROOT) -> list[str]:
    mode = validate_config(config)
    lines = [
        f"Workflow mode: {mode}",
        f"Spec Kit enabled: {'yes' if spec_kit_enabled(config) else 'no'}",
    ]

    configured = config.get("active_feature")
    if isinstance(configured, str) and configured.strip():
        lines.append(f"Configured active feature: {configured.strip()}")
    else:
        lines.append("Configured active feature: <not set>")

    try:
        feature = resolve_feature(root, config)
    except GateError as exc:
        lines.append(f"Resolved active feature: <not resolved: {exc}>")
    else:
        lines.append(f"Resolved active feature: {display_path(feature, root)}")

    lines.append(
        "Allowed change classes: " + ", ".join(sorted(ALLOWED_CHANGE_CLASSES[mode]))
    )
    return lines


def complete(config: dict[str, Any], *, root: Path = DEFAULT_ROOT) -> list[str]:
    mode = validate_config(config)

    missing_commands = unresolved_commands(config)
    if missing_commands:
        raise GateError(
            "Cannot claim full validation; commands are unresolved: "
            + ", ".join(missing_commands)
        )

    handoff = root / "dev" / "HANDOFF.md"
    if not handoff.is_file():
        raise GateError(f"Missing {display_path(handoff, root)}.")

    lines = ["Configuration-level completion checks passed."]

    if mode == "agent-managed":
        feature = resolve_feature(root, config)
        validate_agent_managed_feature(root, feature)
        tasks_text = (feature / "tasks.md").read_text(encoding="utf-8")
        matches = list(CHECKBOX_RE.finditer(tasks_text))
        incomplete = [
            match.group(0).strip()
            for match in matches
            if match.group("state").lower() != "x"
        ]
        if incomplete:
            raise GateError(
                f"Agent-managed feature still has {len(incomplete)} incomplete task(s)."
            )
        lines.append("Agent-managed feature task checklist: PASS")

    lines.append(
        "Run the configured full_check command and inspect the final Git diff."
    )
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate repository workflow prerequisites."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=argparse.SUPPRESS,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")

    pre = subparsers.add_parser("pre-implement")
    pre.add_argument(
        "--change-class",
        choices=tuple(sorted(CHANGE_CLASSES)),
        required=True,
    )
    pre.add_argument(
        "--feature",
        help=(
            "Feature directory override, for example "
            "specs/003-project-idea-workspace"
        ),
    )

    subparsers.add_parser("complete")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()

    try:
        config = load_config(root)

        if args.command == "status":
            lines = status(config, root=root)
        elif args.command == "pre-implement":
            lines = pre_implement(
                config,
                args.change_class,
                root=root,
                explicit_feature=args.feature,
            )
        elif args.command == "complete":
            lines = complete(config, root=root)
        else:
            raise GateError(f"Unknown command: {args.command}")
    except GateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
