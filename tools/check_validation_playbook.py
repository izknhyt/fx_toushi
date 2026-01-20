"""Validate validation playbook YAML structure."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def _load_payload(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    loader = getattr(yaml, "safe_load", None)
    if loader:
        payload = loader(text) or {}
        if isinstance(payload, dict):
            return payload
    if text.lstrip().startswith("# JSON"):
        text = text.split("\n", 1)[1]
    return json.loads(text)


def _category_matches(
    payload: dict[str, object], *, category: str | None, path: Path
) -> bool:
    if not category:
        return True
    payload_category = str(payload.get("category") or "")
    playbook_id = str(payload.get("validation_playbook_id") or path.stem)
    return category in payload_category or category in playbook_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", help="Filter by playbook category or id token.")
    args = parser.parse_args()

    root = Path("docs") / "validation_playbook"
    if not root.exists():
        print("validation_playbook directory missing", file=sys.stderr)
        return 1
    errors: list[str] = []
    checked = 0
    for path in sorted(root.glob("*.yaml")):
        payload = {}
        try:
            payload = _load_payload(path)
        except Exception as exc:
            errors.append(f"{path}: invalid payload ({exc})")
            continue
        if not _category_matches(payload, category=args.category, path=path):
            continue
        checked += 1
        playbook_id = payload.get("validation_playbook_id")
        expected = path.stem
        if playbook_id != expected:
            errors.append(
                f"{path}: validation_playbook_id '{playbook_id}' != '{expected}'"
            )
        entries = payload.get("entries")
        if entries is None:
            errors.append(f"{path}: missing entries")
        elif not isinstance(entries, list):
            errors.append(f"{path}: entries must be a list")
    if args.category and checked == 0:
        errors.append(f"no playbooks matched category '{args.category}'")
    if errors:
        print("Validation playbook check failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1
    if args.category:
        print(f"Validation playbook check ok ({checked} files, category={args.category}).")
    else:
        print(f"Validation playbook check ok ({len(list(root.glob('*.yaml')))} files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
