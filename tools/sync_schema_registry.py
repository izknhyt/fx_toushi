"""Sync docs/schemas into schema/ runtime mirror.

This keeps runtime schemas aligned with the registry used for governance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _sync_schema_registry(docs_dir: Path, runtime_dir: Path) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    for doc_path in docs_dir.glob("*.schema.json"):
        runtime_path = runtime_dir / doc_path.name
        if runtime_path.is_symlink():
            continue
        target = Path("..") / "docs" / "schemas" / doc_path.name
        if not runtime_path.exists():
            runtime_path.symlink_to(target)
            continue
        runtime_path.write_text(doc_path.read_text(encoding="utf-8"), encoding="utf-8")

    for runtime_path in runtime_dir.glob("*.schema.json"):
        doc_path = docs_dir / runtime_path.name
        if doc_path.exists():
            continue
        if runtime_path.is_symlink():
            runtime_path.unlink()
            continue
        runtime_path.unlink()


def _diff_schema_registry(docs_dir: Path, runtime_dir: Path) -> list[str]:
    mismatches: list[str] = []
    for doc_path in docs_dir.glob("*.schema.json"):
        runtime_path = runtime_dir / doc_path.name
        if not runtime_path.exists():
            mismatches.append(f"missing runtime schema: {runtime_path}")
            continue
        docs_schema = json.loads(doc_path.read_text(encoding="utf-8"))
        runtime_schema = json.loads(runtime_path.read_text(encoding="utf-8"))
        if docs_schema != runtime_schema:
            mismatches.append(f"schema mismatch: {doc_path.name}")
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync docs/schemas to schema/")
    parser.add_argument("--check", action="store_true", help="Only report mismatches")
    args = parser.parse_args()

    docs_dir = Path("docs") / "schemas"
    runtime_dir = Path("schema")

    if args.check:
        mismatches = _diff_schema_registry(docs_dir, runtime_dir)
        if mismatches:
            for line in mismatches:
                print(line)
            return 1
        return 0

    _sync_schema_registry(docs_dir, runtime_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
