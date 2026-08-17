from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TEXT_EXTENSIONS = {".md", ".py", ".json", ".txt", ".yaml", ".yml", ".toml", ".html", ".css", ".js"}


@dataclass(frozen=True)
class ScanRule:
    name: str
    severity: str
    regex: re.Pattern[str]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def prepare_target(repo_root: Path, target: Path, force: bool) -> None:
    if target == repo_root or target.is_relative_to(repo_root):
        raise SystemExit("Refusing to export inside the canonical repository.")
    if target.exists():
        if (target / ".git").exists():
            raise SystemExit("Refusing to export into a target containing .git metadata.")
        if not force:
            raise SystemExit(f"Target exists: {target}; use --force to refresh it.")
        for child in target.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    else:
        target.mkdir(parents=True)


def excluded(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path.replace('\\', '/'), pattern) for pattern in patterns)


def copy_manifest(repo_root: Path, target: Path, manifest: dict[str, Any]) -> None:
    excludes = manifest.get("exclude_globs", [])
    sources: list[Path] = [repo_root / rel for rel in manifest.get("copy_files", [])]
    for rel in manifest.get("copy_dirs", []):
        sources.extend(path for path in sorted((repo_root / rel).rglob('*')) if path.is_file())
    for src in sources:
        rel = src.relative_to(repo_root).as_posix()
        if excluded(rel, excludes):
            continue
        if not src.is_file():
            raise SystemExit(f"Missing public source file: {rel}")
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def load_rules(path: Path) -> list[ScanRule]:
    payload = load_json(path)
    return [ScanRule(item["name"], item["severity"], re.compile(item["regex"])) for item in payload.get("rules", [])]


def scan_bundle(target: Path, rules: list[ScanRule]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in sorted(target.rglob('*')):
        if not path.is_file() or '.git' in path.parts or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for rule in rules:
                if rule.regex.search(line):
                    findings.append({"path": path.relative_to(target).as_posix(), "line": line_no, "severity": rule.severity, "rule": rule.name})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a public-safe PowerPoint Visual Archive Viewer working tree.")
    parser.add_argument("target_dir")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    target = Path(args.target_dir).expanduser().resolve()
    prepare_target(repo_root, target, args.force)
    copy_manifest(repo_root, target, load_json(repo_root / "publishing/public_bundle_manifest.json"))
    shutil.copy2(repo_root / "publishing/templates/public-README.md", target / "README.md")
    findings = scan_bundle(target, load_rules(repo_root / "publishing/private_scan_patterns.json"))
    high = [item for item in findings if item["severity"] == "high"]
    print(f"Public bundle refreshed at: {target}")
    print(f"Private-data scan findings: {len(findings)}")
    for finding in findings:
        print(f"[{finding['severity']}] {finding['path']}:{finding['line']} ({finding['rule']})")
    return 2 if high else 0


if __name__ == "__main__":
    raise SystemExit(main())
