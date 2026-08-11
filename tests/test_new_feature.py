from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "new_feature.py"
SPEC = importlib.util.spec_from_file_location("new_feature", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
new_feature = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(new_feature)


def configure_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(new_feature, "ROOT", tmp_path)
    monkeypatch.setattr(new_feature, "CONFIG", tmp_path / "PROJECT_WORKFLOW.json")
    monkeypatch.setattr(
        new_feature,
        "TEMPLATE",
        tmp_path / "specs" / "000-template-feature",
    )
    monkeypatch.setattr(new_feature, "HANDOFF", tmp_path / "dev" / "HANDOFF.md")


def create_base(tmp_path: Path) -> None:
    template = tmp_path / "specs" / "000-template-feature"
    template.mkdir(parents=True)
    for name in ("spec.md", "plan.md", "tasks.md"):
        (template / name).write_text(
            "# {{FEATURE_TITLE}}\n\n"
            "Feature: {{FEATURE_PATH}}\n"
            "Milestone: {{MILESTONE_ID}}\n"
            "Requirements: {{REQUIREMENT_IDS}}\n",
            encoding="utf-8",
        )

    (tmp_path / "spec").mkdir()
    (tmp_path / "spec" / "REQUIREMENTS.md").write_text(
        "REQ-IDEA-001\nREQ-IDEA-002\n",
        encoding="utf-8",
    )
    (tmp_path / "ROADMAP.md").write_text("M010\n", encoding="utf-8")
    (tmp_path / "PROJECT_WORKFLOW.json").write_text(
        json.dumps({"workflow_mode": "agent-managed", "active_feature": None}),
        encoding="utf-8",
    )


def test_creates_next_feature_and_activates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_root(monkeypatch, tmp_path)
    create_base(tmp_path)

    result = new_feature.main(
        [
            "project-ideas",
            "--title",
            "Project Ideas",
            "--milestone",
            "M010",
            "--requirements",
            "REQ-IDEA-001",
            "REQ-IDEA-002",
        ]
    )

    assert result == 0
    feature = tmp_path / "specs" / "001-project-ideas"
    assert (feature / "spec.md").is_file()
    assert "Project Ideas" in (feature / "spec.md").read_text(encoding="utf-8")
    config = json.loads((tmp_path / "PROJECT_WORKFLOW.json").read_text(encoding="utf-8"))
    assert config["active_feature"] == "specs/001-project-ideas"
    handoff = (tmp_path / "dev" / "HANDOFF.md").read_text(encoding="utf-8")
    assert "specs/001-project-ideas" in handoff
    assert "Project Ideas" in handoff
    assert "living working documents" in handoff


def test_explicit_number_is_supported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_root(monkeypatch, tmp_path)
    create_base(tmp_path)

    result = new_feature.main(
        [
            "project-ideas",
            "--title",
            "Project Ideas",
            "--milestone",
            "M010",
            "--requirements",
            "REQ-IDEA-001",
            "--number",
            "7",
        ]
    )

    assert result == 0
    assert (tmp_path / "specs" / "007-project-ideas").is_dir()


def test_unknown_requirement_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_root(monkeypatch, tmp_path)
    create_base(tmp_path)

    result = new_feature.main(
        [
            "project-ideas",
            "--title",
            "Project Ideas",
            "--milestone",
            "M010",
            "--requirements",
            "REQ-MISSING-001",
        ]
    )

    assert result == 2
    assert not (tmp_path / "specs" / "001-project-ideas").exists()


def test_unknown_milestone_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_root(monkeypatch, tmp_path)
    create_base(tmp_path)

    result = new_feature.main(
        [
            "project-ideas",
            "--title",
            "Project Ideas",
            "--milestone",
            "M999",
            "--requirements",
            "REQ-IDEA-001",
        ]
    )

    assert result == 2


def test_invalid_slug_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_root(monkeypatch, tmp_path)
    create_base(tmp_path)

    result = new_feature.main(
        [
            "Project Ideas",
            "--title",
            "Project Ideas",
            "--milestone",
            "M010",
            "--requirements",
            "REQ-IDEA-001",
        ]
    )

    assert result == 2
