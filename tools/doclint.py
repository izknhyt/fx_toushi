"""Simple DocLint checks for runbooks/templates."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import re
import yaml


@dataclass(slots=True)
class DocLintIssue:
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


class DocLint:
    def __init__(self, *, category: str, require_front_matter: bool = False) -> None:
        self._category = category
        self._require_front_matter = require_front_matter

    def lint_paths(self, paths: list[Path]) -> list[DocLintIssue]:
        issues: list[DocLintIssue] = []
        for path in paths:
            text = path.read_text(encoding="utf-8")
            front_matter, body = _split_front_matter(text)
            title_line = _find_title(body)
            if not title_line:
                issues.append(DocLintIssue(path.as_posix(), "missing H1 title"))
            if front_matter is None:
                issues.append(DocLintIssue(path.as_posix(), "front matter parse error"))
            if self._require_front_matter and not front_matter:
                issues.append(DocLintIssue(path.as_posix(), "front matter missing"))
            if self._category == "ux":
                issues.extend(_lint_ux_colors(path, text))
        return issues


def _split_front_matter(text: str) -> tuple[dict[str, object] | None, str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}, text
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}, text
    front_matter_raw = "\n".join(lines[1:end_idx])
    try:
        data = yaml.safe_load(front_matter_raw) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return None, text
    body = "\n".join(lines[end_idx + 1 :]).lstrip()
    return data, body


def _find_title(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None


def _collect_paths(category: str, *, root: Path) -> list[Path]:
    if category == "runbook":
        target = root / "docs" / "runbooks"
    elif category == "ux":
        path = root / "docs" / "ux_feedback.md"
        return [path] if path.exists() else []
    elif category == "template":
        target = root / "docs" / "templates"
    else:
        target = root / "docs"
    if not target.exists():
        return []
    return sorted(target.rglob("*.md"))


def main() -> int:
    parser = argparse.ArgumentParser(description="DocLint checks for DocOps.")
    parser.add_argument("--category", default="runbook", help="runbook|template|ux|all")
    parser.add_argument(
        "--require-front-matter",
        action="store_true",
        help="Require YAML front matter in each document",
    )
    parser.add_argument("--root", default=".", help="Repository root path")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    root = Path(args.root)
    category = args.category
    paths = _collect_paths(category, root=root)
    lint = DocLint(category=category, require_front_matter=args.require_front_matter)
    issues = lint.lint_paths(paths)
    payload = {"status": "ok" if not issues else "error", "issues": [i.to_dict() for i in issues]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for issue in issues:
            print(f"{issue.path}: {issue.message}")
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())


def _lint_ux_colors(path: Path, text: str) -> list[DocLintIssue]:
    issues: list[DocLintIssue] = []
    allowed = {"#FF5F57", "#0A84FF", "#30D158"}
    for match in re.findall(r"#[0-9a-fA-F]{6}", text):
        if match.upper() not in allowed:
            issues.append(DocLintIssue(path.as_posix(), f"unsupported color {match}"))
    return issues
