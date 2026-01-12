#!/usr/bin/env python3
"""Append an entry to the Update Log in docs/development_plan.md."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_PATH = Path("docs/development_plan.md")


def _utc_minute_stamp() -> str:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    return now.strftime("%Y-%m-%dT%H:%MZ")


def _find_update_log_bounds(lines: list[str]) -> tuple[int, int]:
    """Return (start_index, end_index) for the Update Log section."""
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == "## Update Log (UTC)":
            start = idx
            break
    if start is None:
        raise ValueError("Update Log section not found.")
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break
    return start, end


def append_update_log(path: Path, message: str, stamp: str | None = None) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    start, end = _find_update_log_bounds(lines)

    stamp_value = stamp or _utc_minute_stamp()
    entry = f"- {stamp_value} — {message}"

    insert_at = end
    # Insert before the next header, after any trailing blanks within the section.
    for idx in range(end - 1, start, -1):
        if lines[idx].strip():
            insert_at = idx + 1
            break

    lines.insert(insert_at, entry)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Append Update Log entry.")
    parser.add_argument("message", help="Log message to append.")
    parser.add_argument(
        "--file",
        default=str(DEFAULT_PATH),
        help="Path to development plan file (default: docs/development_plan.md).",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="UTC timestamp override (YYYY-MM-DDTHH:MMZ).",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    append_update_log(path, args.message.strip(), stamp=args.timestamp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
