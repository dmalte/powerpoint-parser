#!/usr/bin/env python3
"""Project-local shim for shared agent-managed feature creation."""

from __future__ import annotations

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _workspace_control_root() -> Path:
    explicit = os.environ.get("WORKSPACE_CONTROL_ROOT")
    candidate = (
        Path(explicit).expanduser().resolve()
        if explicit
        else (PROJECT_ROOT.parent / "workspace-control").resolve()
    )
    required = candidate / "workflow_engine" / "new_feature.py"
    if not required.is_file():
        raise RuntimeError(
            "Shared workflow engine was not found. Set WORKSPACE_CONTROL_ROOT "
            f"or provide sibling workspace-control; expected {required}"
        )
    return candidate


WORKSPACE_CONTROL_ROOT = _workspace_control_root()
if str(WORKSPACE_CONTROL_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_CONTROL_ROOT))

from workflow_engine import new_feature as _engine  # noqa: E402

for _name in dir(_engine):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_engine, _name)

ROOT = PROJECT_ROOT
CONFIG = ROOT / "PROJECT_WORKFLOW.json"
TEMPLATE = ROOT / "specs" / "000-template-feature"
HANDOFF = ROOT / "dev" / "HANDOFF.md"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(ROOT).resolve()
    if "--root" not in args:
        args = ["--root", str(root), *args]
    return _engine.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
