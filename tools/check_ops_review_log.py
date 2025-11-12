"""Utility script to validate the ops review ledger required by RUN-POST-03."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LEDGER_PATH = Path("logs/ops/review.log")


@dataclass(frozen=True)
class LedgerEntry:
    """Structured view over a single review log line."""

    line_no: int
    timestamp: str
    review_type: str
    follow_up_id: str
    finding_summary: str
    impact_summary: str
    remediation_status: str
    evidence_links: str


def _parse_entries(path: Path) -> list[LedgerEntry]:
    entries: list[LedgerEntry] = []
    for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = [field.strip() for field in stripped.split("|")]
        if len(parts) != 7:
            raise ValueError(
                f"Line {idx} must contain 7 pipe-delimited fields, found {len(parts)}: {raw}"
            )
        entries.append(
            LedgerEntry(
                line_no=idx,
                timestamp=parts[0],
                review_type=parts[1],
                follow_up_id=parts[2],
                finding_summary=parts[3],
                impact_summary=parts[4],
                remediation_status=parts[5],
                evidence_links=parts[6],
            )
        )
    return entries


def _render_summary(entries: Iterable[LedgerEntry]) -> str:
    items = list(entries)
    if not items:
        return "0 entries recorded yet"
    latest = items[-1]
    return (
        f"{len(items)} entries (latest #{latest.follow_up_id} at {latest.timestamp} "
        f"→ {latest.remediation_status})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the existence and schema of logs/ops/review.log"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=LEDGER_PATH,
        help="Override ledger path (default: logs/ops/review.log)",
    )
    parser.add_argument(
        "--require",
        action="store_true",
        help="Exit with status 1 if the ledger is missing or malformed",
    )
    args = parser.parse_args()

    path: Path = args.path
    if not path.exists():
        message = (
            f"[ops.review_log] missing at {path.as_posix()} – "
            "follow RUN-POST-03 to recreate and log an Ops issue."
        )
        print(message, file=sys.stderr)
        sys.exit(1 if args.require else 0)

    try:
        entries = _parse_entries(path)
    except ValueError as exc:
        print(f"[ops.review_log] format error: {exc}", file=sys.stderr)
        sys.exit(1)

    summary = _render_summary(entries)
    print(f"[ops.review_log] {summary}")


if __name__ == "__main__":
    main()
