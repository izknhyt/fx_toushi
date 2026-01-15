#!/usr/bin/env python3
"""Generate Ops workload summaries from ops_worklog + automation_effect logs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ops workload summary metrics.")
    parser.add_argument(
        "--worklog",
        type=Path,
        default=Path("ops_worklog.jsonl"),
        help="Path to ops_worklog.jsonl",
    )
    parser.add_argument(
        "--automation",
        type=Path,
        default=Path("automation_effect.jsonl"),
        help="Path to automation_effect.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("metrics/ops_workload.json"),
        help="Output JSON file",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional Markdown report output path",
    )
    args = parser.parse_args()

    workload = _load_worklog(args.worklog)
    totals = _summarize_totals(workload)
    automation_gain = _sum_automation_gain(args.automation)
    payload = {
        "generated_at": _utc_now(),
        "totals": {
            "minutes": totals["minutes"],
            "automation_gain_min": automation_gain,
        },
        "tasks": totals["tasks"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(_render_report(payload), encoding="utf-8")

    return 0


def _load_worklog(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    entries: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        entries.append(data)
    return entries


def _summarize_totals(entries: list[dict[str, object]]) -> dict[str, object]:
    totals = {"minutes": 0, "tasks": {}}
    task_minutes: dict[str, list[int]] = {}
    for entry in entries:
        task = str(entry.get("task", "unknown"))
        try:
            duration = int(entry.get("duration_min", 0))
        except (TypeError, ValueError):
            duration = 0
        totals["minutes"] += duration
        task_minutes.setdefault(task, []).append(duration)
    for task, durations in task_minutes.items():
        totals["tasks"][task] = {
            "median_min": int(median(durations)),
            "p90_min": int(_percentile(durations, 90)),
            "count": len(durations),
        }
    return totals


def _sum_automation_gain(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            total += int(data.get("gain_min", 0))
        except (TypeError, ValueError):
            continue
    return total


def _percentile(values: list[int], percentile_value: int) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * (percentile_value / 100.0)
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return float(values_sorted[f])
    d0 = values_sorted[f] * (c - k)
    d1 = values_sorted[c] * (k - f)
    return d0 + d1


def _render_report(payload: dict[str, object]) -> str:
    totals = payload.get("totals", {})
    tasks = payload.get("tasks", {})
    lines = [
        "# Ops Workload Summary",
        "",
        f"- Generated At: {payload.get('generated_at')}",
        f"- Total Minutes: {totals.get('minutes')}",
        f"- Automation Gain (min): {totals.get('automation_gain_min')}",
        "",
        "## Task Stats",
        "| Task | Median (min) | P90 (min) | Count |",
        "| --- | --- | --- | --- |",
    ]
    if isinstance(tasks, dict) and tasks:
        for task, stats in tasks.items():
            lines.append(
                f"| {task} | {stats.get('median_min')} | {stats.get('p90_min')} | {stats.get('count')} |"
            )
    else:
        lines.append("| n/a | n/a | n/a | 0 |")
    lines.append("")
    return "\n".join(lines)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
