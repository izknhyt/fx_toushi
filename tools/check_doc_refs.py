#!/usr/bin/env python3
"""Fail if deprecated doc paths are referenced outside docs/archive/."""

from __future__ import annotations

from pathlib import Path


DEPRECATED = [
    "docs/change_requests/",
    "docs/prompt_packages/",
    "docs/implementation_packets/",
    "docs/releases/",
    "docs/review_log.md",
]


def should_skip(path: Path) -> bool:
    return "docs/archive" in str(path)


def main() -> int:
    root = Path("docs")
    violations: list[str] = []

    for path in root.rglob("*.md"):
        if should_skip(path):
            continue
        text = path.read_text(encoding="utf-8")
        for token in DEPRECATED:
            if token in text:
                violations.append(f"{path}: {token}")

    if violations:
        print("Deprecated doc references found:")
        for entry in violations:
            print(f"- {entry}")
        return 1

    print("No deprecated doc references found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
