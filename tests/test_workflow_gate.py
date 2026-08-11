from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "workflow_gate.py"
SPEC = importlib.util.spec_from_file_location("workflow_gate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def write_config(
    root: Path,
    *,
    mode: str = "agent-managed",
    active_feature: str | None = "specs/003-project-idea-workspace",
    spec_enabled: bool = False,
) -> dict:
    config = {
        "schema_version": "1.0",
        "workflow_mode": mode,
        "spec_kit": {
            "enabled": spec_enabled,
            "integration": "copilot",
            "version_pin": "0.14.2",
            "default_feature_path": "full",
            "allow_direct_small_changes": True,
        },
        "commands": {
            "setup": "python -m pip install -e .",
            "run": ".\\start_project_hub.ps1",
            "fast_check": "python -m pytest tests/test_workflow_gate.py -q",
            "test": "python -m pytest",
            "full_check": "python -m pytest",
        },
        "git": {
            "agent_may_create_branch": True,
            "agent_may_commit_locally": True,
            "agent_may_push": False,
            "agent_may_merge": False,
            "agent_may_create_tags": False,
            "agent_may_publish_release": False,
        },
        "project_constraints": [],
    }
    if active_feature is not None:
        config["active_feature"] = active_feature

    (root / "PROJECT_WORKFLOW.json").write_text(
        json.dumps(config, indent=2),
        encoding="utf-8",
    )
    return config


def create_agent_managed_feature(
    root: Path,
    relative: str = "specs/003-project-idea-workspace",
    *,
    requirement: str = "REQ-IDEA-001",
    milestone: str = "M010",
) -> Path:
    feature = root / relative
    feature.mkdir(parents=True, exist_ok=True)

    (feature / "spec.md").write_text(
        f"# Project Idea Workspace\n\n"
        f"- Milestone: {milestone}\n"
        f"- Requirements: {requirement}\n\n"
        "## Objective\n\nCreate Markdown-backed project ideas.\n",
        encoding="utf-8",
    )
    (feature / "plan.md").write_text(
        f"# Plan\n\nMilestone: {milestone}\n\n"
        f"Implement {requirement} using the existing architecture.\n\n"
        "## Validation\n\nRun focused and full tests.\n",
        encoding="utf-8",
    )
    (feature / "tasks.md").write_text(
        f"# Tasks\n\n- [ ] T001 Implement storage for {requirement}\n",
        encoding="utf-8",
    )

    (root / "spec").mkdir(parents=True, exist_ok=True)
    (root / "spec" / "REQUIREMENTS.md").write_text(
        f"# Requirements\n\n- [ ] **{requirement}** — Create project ideas.\n",
        encoding="utf-8",
    )
    (root / "ROADMAP.md").write_text(
        "# Roadmap\n\n"
        f"| {milestone} | Project idea workspace | Outcome | — | active | "
        f"`{relative}` |\n",
        encoding="utf-8",
    )
    (root / "dev").mkdir(parents=True, exist_ok=True)
    (root / "dev" / "HANDOFF.md").write_text(
        "# Handoff\n\nNo interrupted work.\n",
        encoding="utf-8",
    )
    return feature


def test_agent_managed_mode_accepts_valid_agent_managed_feature(tmp_path: Path) -> None:
    config = write_config(tmp_path)
    create_agent_managed_feature(tmp_path)

    lines = gate.pre_implement(config, "feature", root=tmp_path)

    assert lines[0] == "Agent-managed feature gate passed."
    assert any("Spec Kit is not required" in line for line in lines)


def test_agent_managed_mode_allows_direct_change(tmp_path: Path) -> None:
    config = write_config(tmp_path)

    lines = gate.pre_implement(config, "direct", root=tmp_path)

    assert lines[0] == "Direct path allowed."


def test_direct_mode_allows_agent_managed_feature(tmp_path: Path) -> None:
    config = write_config(tmp_path, mode="direct")
    create_agent_managed_feature(tmp_path)

    lines = gate.pre_implement(config, "feature", root=tmp_path)

    assert lines[0] == "Agent-managed feature gate passed."


def test_missing_active_feature_fails_when_none_can_be_inferred(
    tmp_path: Path,
) -> None:
    config = write_config(tmp_path, active_feature=None)

    with pytest.raises(gate.GateError, match="Could not resolve an active feature"):
        gate.pre_implement(config, "feature", root=tmp_path)


def test_explicit_feature_overrides_configured_feature(tmp_path: Path) -> None:
    config = write_config(
        tmp_path,
        active_feature="specs/999-does-not-exist",
    )
    create_agent_managed_feature(tmp_path, "specs/004-explicit-feature")

    lines = gate.pre_implement(
        config,
        "feature",
        root=tmp_path,
        explicit_feature="specs/004-explicit-feature",
    )

    assert any("specs/004-explicit-feature" in line for line in lines)


@pytest.mark.parametrize("missing_name", ["spec.md", "plan.md", "tasks.md"])
def test_missing_required_artifact_fails(
    tmp_path: Path,
    missing_name: str,
) -> None:
    config = write_config(tmp_path)
    feature = create_agent_managed_feature(tmp_path)
    (feature / missing_name).unlink()

    with pytest.raises(gate.GateError, match="Missing required feature artifacts"):
        gate.pre_implement(config, "feature", root=tmp_path)


def test_empty_required_artifact_fails(tmp_path: Path) -> None:
    config = write_config(tmp_path)
    feature = create_agent_managed_feature(tmp_path)
    (feature / "plan.md").write_text("   \n", encoding="utf-8")

    with pytest.raises(gate.GateError, match="Empty required feature artifacts"):
        gate.pre_implement(config, "feature", root=tmp_path)


def test_tasks_must_contain_checkbox(tmp_path: Path) -> None:
    config = write_config(tmp_path)
    feature = create_agent_managed_feature(tmp_path)
    (feature / "tasks.md").write_text(
        "# Tasks\n\nImplement the feature.\n",
        encoding="utf-8",
    )

    with pytest.raises(gate.GateError, match="Markdown checkbox"):
        gate.pre_implement(config, "feature", root=tmp_path)


def test_feature_path_outside_specs_fails(tmp_path: Path) -> None:
    config = write_config(tmp_path, active_feature=None)
    feature = create_agent_managed_feature(tmp_path, "outside-feature")

    with pytest.raises(gate.GateError, match="inside specs"):
        gate.pre_implement(
            config,
            "feature",
            root=tmp_path,
            explicit_feature=feature,
        )


def test_hybrid_gated_rejects_feature_change_class(tmp_path: Path) -> None:
    config = write_config(tmp_path, mode="hybrid-gated")
    create_agent_managed_feature(tmp_path)

    with pytest.raises(gate.GateError, match="does not permit change class"):
        gate.pre_implement(config, "feature", root=tmp_path)


def test_strict_rejects_feature_change_class(tmp_path: Path) -> None:
    config = write_config(tmp_path, mode="strict")
    create_agent_managed_feature(tmp_path)

    with pytest.raises(gate.GateError, match="does not permit change class"):
        gate.pre_implement(config, "feature", root=tmp_path)


def test_agent_managed_mode_does_not_require_specify_directory(tmp_path: Path) -> None:
    config = write_config(tmp_path, spec_enabled=False)
    create_agent_managed_feature(tmp_path)

    assert not (tmp_path / ".specify").exists()
    lines = gate.pre_implement(config, "feature", root=tmp_path)

    assert lines[0] == "Agent-managed feature gate passed."


def test_unknown_requirement_reference_fails(tmp_path: Path) -> None:
    config = write_config(tmp_path)
    feature = create_agent_managed_feature(tmp_path)
    (feature / "spec.md").write_text(
        "# Feature\n\nMilestone: M010\nRequirement: REQ-MISSING-999\n",
        encoding="utf-8",
    )

    with pytest.raises(gate.GateError, match="not found"):
        gate.pre_implement(config, "feature", root=tmp_path)


def test_unknown_milestone_reference_fails(tmp_path: Path) -> None:
    config = write_config(tmp_path)
    feature = create_agent_managed_feature(tmp_path)
    for name in ("spec.md", "plan.md", "tasks.md"):
        path = feature / name
        path.write_text(
            path.read_text(encoding="utf-8").replace("M010", "M999"),
            encoding="utf-8",
        )

    with pytest.raises(gate.GateError, match="milestone IDs not found"):
        gate.pre_implement(config, "feature", root=tmp_path)


def test_multiple_unfinished_features_are_not_ambiguous_when_configured(
    tmp_path: Path,
) -> None:
    config = write_config(
        tmp_path,
        active_feature="specs/003-project-idea-workspace",
    )
    create_agent_managed_feature(tmp_path, "specs/003-project-idea-workspace")
    second = tmp_path / "specs" / "009-other-feature"
    second.mkdir(parents=True)
    (second / "spec.md").write_text("# Other\n", encoding="utf-8")

    lines = gate.pre_implement(config, "feature", root=tmp_path)

    assert any("003-project-idea-workspace" in line for line in lines)


def test_short_spec_kit_work_requires_enabled_spec_kit(tmp_path: Path) -> None:
    config = write_config(
        tmp_path,
        mode="hybrid-gated",
        spec_enabled=False,
    )
    create_agent_managed_feature(tmp_path)

    with pytest.raises(gate.GateError, match="spec_kit.enabled is false"):
        gate.pre_implement(config, "short", root=tmp_path)
