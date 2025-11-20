#!/usr/bin/env python3
"""Generate Edge Watch weekly Markdown from spread/correlation metrics."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_SPREAD_PATH = Path("metrics/spread_guard.jsonl")
DEFAULT_CORRELATION_PATH = Path("metrics/correlation_guard.jsonl")
DEFAULT_OUTPUT_DIR = Path("reports/ops")


def _read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, object]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if limit:
        lines = lines[-limit:]
    entries: list[dict[str, object]] = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _summarise_spread(entries: Sequence[dict[str, object]]) -> list[str]:
    summary: list[str] = []
    for entry in entries:
        desc = (
            f"- {entry.get('ts','n/a')}: {entry.get('symbol','?')} "
            f"spread={entry.get('spread_bps','?')} bps "
            f"state={entry.get('cooldown_state','normal')}"
        )
        summary.append(desc)
    return summary


def _summarise_correlation(entries: Sequence[dict[str, object]]) -> list[str]:
    summary: list[str] = []
    for entry in entries:
        desc = (
            f"- {entry.get('ts','n/a')}: bucket={entry.get('bucket','global')} "
            f"r_eff={entry.get('r_eff','?')} guard={entry.get('guard','none')}"
        )
        summary.append(desc)
    return summary


def _render_report(
    *,
    week: str,
    spread_entries: list[dict[str, object]],
    correlation_entries: list[dict[str, object]],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"edge_watch_{week}.md"
    today = datetime.now(timezone.utc).date()
    content = [
        f"# Edge Watch Summary — {week}",
        "",
        f"- Generated: {today.isoformat()}",
        f"- Spread Samples: {len(spread_entries)}",
        f"- Correlation Samples: {len(correlation_entries)}",
        "",
        "## Spread Guard Highlights",
        "",
    ]
    content.extend(_summarise_spread(spread_entries) or ["- No samples found."])
    content.extend(
        [
            "",
            "## Correlation Guard Highlights",
            "",
        ]
    )
    content.extend(_summarise_correlation(correlation_entries) or ["- No samples found."])
    content.extend(
        [
            "",
            "## Next Actions",
            "",
            "- Review RUN-SPREAD-03 evidence and confirm cooldown reset.",
            "- Execute RUN-CORR-02 checklist if any bucket exceeds guard threshold.",
        ]
    )
    path.write_text("\n".join(content) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", help="ISO week format YYYY-Www", default=None)
    parser.add_argument("--spread-path", type=Path, default=DEFAULT_SPREAD_PATH, help="metrics/spread_guard.jsonl")
    parser.add_argument(
        "--correlation-path",
        type=Path,
        default=DEFAULT_CORRELATION_PATH,
        help="metrics/correlation_guard.jsonl",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of samples to include from each metrics file.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for reports/ops outputs.",
    )
    args = parser.parse_args()
    today = date.today()
    iso = today.isocalendar()
    iso_year = getattr(iso, "year", iso[0])
    iso_week = getattr(iso, "week", iso[1])
    week = args.week or f"{iso_year}-W{iso_week:02d}"
    spread_entries = _read_jsonl(args.spread_path, args.limit)
    correlation_entries = _read_jsonl(args.correlation_path, args.limit)
    report = _render_report(
        week=week,
        spread_entries=spread_entries,
        correlation_entries=correlation_entries,
        output_dir=args.out_dir,
    )
    print(f"Edge Watch report generated: {report}")


if __name__ == "__main__":
    main()
