"""Compare freshly generated metrics with a baseline and emit Markdown evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


KEY_FIELDS = [
    ("metrics", "pf_all", "PF (All)"),
    ("metrics", "sharpe_all", "Sharpe (All)"),
    ("metrics", "max_drawdown_all", "MaxDD (All)"),
    ("oos", "pf", "PF (OOS)"),
    ("oos", "sharpe", "Sharpe (OOS)"),
    ("oos", "max_drawdown", "MaxDD (OOS)"),
]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Metrics file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _extract(data: dict[str, Any], section: str, key: str) -> float | None:
    section_data = data.get(section) or {}
    value = section_data.get(key)
    return float(value) if value is not None else None


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_delta(current: float | None, baseline: float | None) -> str:
    if current is None or baseline is None:
        return "n/a"
    delta = current - baseline
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.4f}"


def _threshold_check(data: dict[str, Any]) -> tuple[bool, list[str]]:
    checks = [
        ("PF_all ≥ 1.18", (_extract(data, "metrics", "pf_all") or 0) >= 1.18),
        ("Sharpe(OOS) ≥ 0.85", (_extract(data, "oos", "sharpe") or 0) >= 0.85),
        ("MaxDD(OOS) ≤ 0.13", (_extract(data, "oos", "max_drawdown") or 1) <= 0.13),
        (
            "BCa PF lower ≥ 1.12",
            ((data.get("bootstrap_ci") or {}).get("pf") or {}).get("lower", 0) >= 1.12,
        ),
        (
            "BCa Sharpe lower ≥ 0.78",
            ((data.get("bootstrap_ci") or {}).get("sharpe") or {}).get("lower", 0) >= 0.78,
        ),
    ]
    descriptions = [f"- [{'x' if passed else ' '}] {label}" for label, passed in checks]
    return all(passed for _, passed in checks), descriptions


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare metrics JSON with a baseline and emit Markdown evidence.")
    parser.add_argument("metrics_path", type=Path, help="Path to the freshly generated metrics JSON")
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Path to the baseline metrics JSON for comparison",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Markdown file that will contain the evaluation summary",
    )
    args = parser.parse_args()

    current = _load_json(args.metrics_path)
    baseline = _load_json(args.baseline)

    lines = [
        f"# Validation Summary ({_now_utc()})",
        "",
        f"- Strategy: `{current.get('strategy', 'unknown')}`",
        f"- Dataset hash: `{current.get('dataset_hash', 'n/a')}`",
        f"- Config hash: `{current.get('config_hash', 'n/a')}`",
        "",
        "## Threshold Checks",
    ]
    _, checklist = _threshold_check(current)
    lines.extend(checklist)

    lines.extend(
        [
            "",
            "## Metric Comparison vs Baseline",
            "| Metric | Current | Baseline | Δ |",
            "| --- | --- | --- | --- |",
        ]
    )

    for section, key, label in KEY_FIELDS:
        current_value = _extract(current, section, key)
        baseline_value = _extract(baseline, section, key)
        current_str = f"{current_value:.4f}" if current_value is not None else "n/a"
        baseline_str = f"{baseline_value:.4f}" if baseline_value is not None else "n/a"
        delta = _format_delta(current_value, baseline_value)
        lines.append(f"| {label} | {current_str} | {baseline_str} | {delta} |")

    output = "\n".join(lines) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(output, encoding="utf-8")
    print(f"Wrote validation summary to {args.out}")


if __name__ == "__main__":
    main()
