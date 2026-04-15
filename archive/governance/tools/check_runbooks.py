"""Run DocLint + RunbookInventory refresh for CI."""

from __future__ import annotations

import argparse

from pathlib import Path

from src.docops.registry import DocsRegistry
from src.docops.runbook_inventory import RunbookInventoryService
from tools.doclint import DocLint, _collect_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Check runbooks and inventory.")
    parser.add_argument("--root", default=".", help="Repository root path")
    parser.add_argument("--no-write", action="store_true", help="Skip writing inventory")
    args = parser.parse_args()

    paths = _collect_paths("runbook", root=Path(args.root))
    issues = DocLint(category="runbook").lint_paths(paths)
    if issues:
        for issue in issues:
            print(f"{issue.path}: {issue.message}")
        return 2

    registry = DocsRegistry()
    registry.sync(no_write=args.no_write)
    RunbookInventoryService(docs_registry=registry).refresh(no_write=args.no_write)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
