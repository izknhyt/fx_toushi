"""Review long-horizon portfolio validation outputs and rank improvement candidates."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.portfolio.allocation_review import build_allocator_hypotheses

DEFAULT_SUMMARY_JSON = (
    PROJECT_ROOT / "reports" / "validation_log" / "usdjpy_long_horizon_validation_run_20260315.json"
)
DEFAULT_VALIDATION_LOG_DIR = PROJECT_ROOT / "reports" / "validation_log"
DEFAULT_ANALYSIS_DIR = PROJECT_ROOT / "reports" / "analysis"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _pf(values: Iterable[float]) -> float | None:
    wins = 0.0
    losses = 0.0
    for value in values:
        if value > 0:
            wins += value
        elif value < 0:
            losses += abs(value)
    if losses == 0:
        return None if wins == 0 else float("inf")
    return round(wins / losses, 4)


def _round_metric(value: float | None) -> float | None:
    if value is None:
        return None
    if value == float("inf"):
        return value
    return round(float(value), 4)


def _year_from_trade(trade: dict[str, Any]) -> str:
    opened_at = str(trade.get("opened_at") or "").strip()
    if len(opened_at) >= 4:
        return opened_at[:4]
    return "unknown"


def _direction_from_trade(trade: dict[str, Any]) -> str:
    direction = str(trade.get("direction") or "").strip().lower()
    return direction or "unknown"


def _summary_from_run_stamp(
    *,
    run_stamp: str,
    validation_log_dir: Path = DEFAULT_VALIDATION_LOG_DIR,
    analysis_dir: Path = DEFAULT_ANALYSIS_DIR,
) -> dict[str, Any]:
    pattern = re.compile(rf"^long_horizon_portfolio_{re.escape(run_stamp)}_(.+)\.json$")
    results: list[dict[str, Any]] = []
    for raw_path in sorted(validation_log_dir.glob(f"long_horizon_portfolio_{run_stamp}_*.json")):
        match = pattern.match(raw_path.name)
        if not match:
            continue
        window_name = match.group(1)
        report_json_path = analysis_dir / f"long_horizon_portfolio_{run_stamp}_{window_name}_report.json"
        report_md_path = analysis_dir / f"long_horizon_portfolio_{run_stamp}_{window_name}_report.md"
        if not report_json_path.exists():
            continue
        report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
        acceptance = report_payload.get("acceptance_gate", {})
        results.append(
            {
                "window_name": window_name,
                "purpose": None,
                "summary": {
                    "pf": report_payload.get("summary", {}).get("pf"),
                    "avg_r": report_payload.get("summary", {}).get("avg_r"),
                    "max_drawdown": report_payload.get("metrics", {}).get("max_drawdown"),
                    "trades": report_payload.get("summary", {}).get("count"),
                    "win_rate": report_payload.get("summary", {}).get("win_rate"),
                },
                "acceptance": {
                    "status": acceptance.get("status"),
                    "checks": acceptance.get("checks", {}),
                },
                "evidence": {
                    "raw": str(raw_path),
                    "report_json": str(report_json_path),
                    "report_md": str(report_md_path),
                },
            }
        )
    return {
        "_source_path": f"run_stamp:{run_stamp}",
        "run_stamp": run_stamp,
        "results": results,
    }


def _summarise_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    r_values = [_safe_float(trade.get("r_multiple")) for trade in trades]
    pnl_values = [_safe_float(trade.get("pnl")) for trade in trades]
    count = len(trades)
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    return {
        "count": count,
        "total_r": round(sum(r_values), 4),
        "avg_r": round(sum(r_values) / count, 4) if count else 0.0,
        "win_rate": round(len(wins) / count, 4) if count else 0.0,
        "pf": _round_metric(_pf(r_values)),
        "total_pnl": round(sum(pnl_values), 2),
        "avg_pnl": round(sum(pnl_values) / count, 2) if count else 0.0,
        "loss_count": len(losses),
    }


def _group_summary(
    trades: list[dict[str, Any]],
    *,
    key_builder,
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        key = key_builder(trade)
        groups[key].append(trade)

    rows: list[dict[str, Any]] = []
    for key, group in groups.items():
        row = {field: value for field, value in zip(fields, key, strict=True)}
        row.update(_summarise_trades(group))
        rows.append(row)
    rows.sort(
        key=lambda item: (
            item.get("total_r", 0.0),
            item.get("avg_r", 0.0),
            -item.get("count", 0),
            "|".join(str(item.get(field, "")) for field in fields),
        )
    )
    return rows


def _negative_rows(rows: list[dict[str, Any]], *, min_count: int = 1) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if int(row.get("count", 0)) >= min_count
        and (
            _safe_float(row.get("total_r")) < 0.0
            or _safe_float(row.get("avg_r")) < 0.0
            or (
                row.get("pf") not in (None, float("inf"))
                and _safe_float(row.get("pf")) < 1.0
            )
        )
    ]


def _build_recommendations(
    *,
    window_name: str,
    top_strategy_drags: list[dict[str, Any]],
    by_strategy_direction: list[dict[str, Any]],
    by_strategy_year: list[dict[str, Any]],
    existing_next_actions: list[str],
) -> list[str]:
    recommendations: list[str] = []
    if top_strategy_drags:
        row = top_strategy_drags[0]
        recommendations.append(
            "Gate or de-prioritize "
            f"`{row['strategy_id']}` in `{window_name}`; "
            f"total_r={row['total_r']}, avg_r={row['avg_r']}, pf={row['pf']}, trades={row['count']}."
        )

    negative_direction_rows = _negative_rows(by_strategy_direction, min_count=5)
    positive_direction_map: dict[tuple[str, str], dict[str, Any]] = {}
    for row in by_strategy_direction:
        if _safe_float(row.get("avg_r")) > 0.0:
            positive_direction_map[(str(row.get("strategy_id")), str(row.get("direction")))] = row
    for row in negative_direction_rows:
        strategy_id = str(row.get("strategy_id"))
        direction = str(row.get("direction"))
        opposite = "short" if direction == "long" else "long"
        if (strategy_id, opposite) in positive_direction_map:
            recommendations.append(
                "Consider directional gating for "
                f"`{strategy_id}` in `{window_name}`; "
                f"`{direction}` is negative (avg_r={row['avg_r']}, pf={row['pf']}, trades={row['count']}) "
                f"while `{opposite}` stays positive."
            )
            break

    negative_years_by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _negative_rows(by_strategy_year, min_count=5):
        negative_years_by_strategy[str(row.get("strategy_id"))].append(row)
    for strategy_id, rows in sorted(
        negative_years_by_strategy.items(),
        key=lambda item: (len(item[1]) * -1, sum(_safe_float(row.get("total_r")) for row in item[1])),
    ):
        if len(rows) < 2:
            continue
        years = ", ".join(str(row.get("year")) for row in rows[:4])
        recommendations.append(
            f"Review regime/session filters for `{strategy_id}`; negative years in `{window_name}` include {years}."
        )
        break

    for action in existing_next_actions:
        if action not in recommendations:
            recommendations.append(action)
    return recommendations[:5]


def build_review(
    summary_payload: dict[str, Any],
    *,
    failed_only: bool = True,
    top_n: int = 5,
    allocation_review_payload: Mapping[str, Any] | Path | str | None = None,
) -> dict[str, Any]:
    allocator_hypotheses = build_allocator_hypotheses(
        allocation_review_payload,
        limit=top_n,
    )
    windows: list[dict[str, Any]] = []
    strategy_persistence: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"failed_windows": 0, "total_r": 0.0, "trades": 0}
    )
    for row in summary_payload.get("results", []):
        acceptance = row.get("acceptance", {})
        status = str(acceptance.get("status") or "unknown")
        if failed_only and status == "pass":
            continue
        evidence = row.get("evidence", {})
        raw_path = Path(str(evidence.get("raw", "")))
        report_json_path = Path(str(evidence.get("report_json", "")))
        if not raw_path.exists() or not report_json_path.exists():
            continue

        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
        report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
        trades = raw_payload.get("trades", [])

        by_strategy = _group_summary(
            trades,
            key_builder=lambda trade: (str(trade.get("strategy_id") or "unknown"),),
            fields=("strategy_id",),
        )
        by_strategy_direction = _group_summary(
            trades,
            key_builder=lambda trade: (
                str(trade.get("strategy_id") or "unknown"),
                _direction_from_trade(trade),
            ),
            fields=("strategy_id", "direction"),
        )
        by_strategy_year = _group_summary(
            trades,
            key_builder=lambda trade: (
                str(trade.get("strategy_id") or "unknown"),
                _year_from_trade(trade),
            ),
            fields=("strategy_id", "year"),
        )

        top_strategy_drags = _negative_rows(by_strategy, min_count=5)[:top_n]
        top_direction_drags = _negative_rows(by_strategy_direction, min_count=5)[:top_n]
        top_strategy_year_drags = _negative_rows(by_strategy_year, min_count=2)[:top_n]

        for drag in top_strategy_drags:
            record = strategy_persistence[str(drag["strategy_id"])]
            record["failed_windows"] += 1
            record["total_r"] += _safe_float(drag.get("total_r"))
            record["trades"] += _safe_int(drag.get("count"))

        windows.append(
            {
                "window_name": row.get("window_name"),
                "purpose": row.get("purpose"),
                "acceptance": acceptance,
                "summary": row.get("summary", {}),
                "weak_points": report_payload.get("weak_points", []),
                "existing_next_actions": report_payload.get("next_actions", []),
                "top_strategy_drags": top_strategy_drags,
                "top_direction_drags": top_direction_drags,
                "top_strategy_year_drags": top_strategy_year_drags,
                "recommendations": _build_recommendations(
                    window_name=str(row.get("window_name")),
                    top_strategy_drags=top_strategy_drags,
                    by_strategy_direction=by_strategy_direction,
                    by_strategy_year=by_strategy_year,
                    existing_next_actions=list(report_payload.get("next_actions", [])),
                ),
                "allocator_hypotheses": allocator_hypotheses,
                "evidence": {
                    "raw": str(raw_path),
                    "report_json": str(report_json_path),
                    "report_md": str(evidence.get("report_md", "")),
                },
            }
        )

    persistent_drags = [
        {
            "strategy_id": strategy_id,
            "failed_windows": payload["failed_windows"],
            "total_r": round(payload["total_r"], 4),
            "trades": payload["trades"],
        }
        for strategy_id, payload in strategy_persistence.items()
    ]
    persistent_drags.sort(key=lambda item: (item["failed_windows"] * -1, item["total_r"], item["strategy_id"]))

    next_steps: list[str] = []
    if persistent_drags:
        top = persistent_drags[0]
        next_steps.append(
            "First rework target: "
            f"`{top['strategy_id']}` appears in {top['failed_windows']} failed windows with total_r={top['total_r']}."
        )
    if windows:
        next_steps.append(
            "Use this review to decide whether to disable a strategy, add directional gating, "
            "or add regime/session filters before the next long-horizon rerun."
        )
    for row in allocator_hypotheses[:2]:
        next_steps.append(
            "Allocator follow-up: "
            f"{row['summary']} -> {row['suggested_action']}."
        )

    return {
        "generated_at_utc": _utc_now(),
        "source_summary_json": summary_payload.get("_source_path"),
        "failed_only": failed_only,
        "window_count": len(windows),
        "persistent_strategy_drags": persistent_drags[:top_n],
        "allocator_hypotheses": allocator_hypotheses,
        "windows": windows,
        "next_steps": next_steps,
    }


def render_review_md(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Long-Horizon Validation Review")
    lines.append("")

    lines.append("## Allocator Hypotheses")
    lines.append("")
    lines.append("| Winner | Group | Bucket | Share % | Reason | Action |")
    lines.append("| --- | --- | --- | ---: | --- | --- |")
    for row in payload.get("allocator_hypotheses", []):
        lines.append(
            f"| `{row['winner_strategy_id']}` | `{row.get('winner_portfolio_group')}` | "
            f"`{row.get('winner_exposure_bucket')}` | {row.get('share_pct')} | "
            f"`{row.get('top_reason_code')}` | `{row.get('suggested_action')}` |"
        )
    if not payload.get("allocator_hypotheses"):
        lines.append("| _none_ | _none_ | _none_ | 0 | _none_ | _none_ |")
    lines.append("")
    lines.append(f"- generated_at_utc: `{payload['generated_at_utc']}`")
    lines.append(f"- source_summary_json: `{payload.get('source_summary_json')}`")
    lines.append(f"- failed_only: `{payload.get('failed_only')}`")
    lines.append("")

    lines.append("## Persistent Drags")
    lines.append("")
    lines.append("| Strategy | Failed windows | Total R | Trades |")
    lines.append("| --- | ---: | ---: | ---: |")
    for row in payload.get("persistent_strategy_drags", []):
        lines.append(
            f"| `{row['strategy_id']}` | {row['failed_windows']} | {row['total_r']} | {row['trades']} |"
        )
    if not payload.get("persistent_strategy_drags"):
        lines.append("| _none_ | 0 | 0 | 0 |")
    lines.append("")

    for window in payload.get("windows", []):
        lines.append(f"## Window `{window['window_name']}`")
        lines.append("")
        summary = window.get("summary", {})
        acceptance = window.get("acceptance", {})
        lines.append(
            f"- purpose/status: `{window.get('purpose')}` / `{acceptance.get('status')}`"
        )
        lines.append(
            f"- pf/avg_r/max_dd/trades: `{summary.get('pf')}` / `{summary.get('avg_r')}` / "
            f"`{summary.get('max_drawdown')}` / `{summary.get('trades')}`"
        )
        lines.append("")

        lines.append("### Strategy Drags")
        lines.append("")
        lines.append("| Strategy | Total R | Avg R | PF | Trades |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for row in window.get("top_strategy_drags", []):
            lines.append(
                f"| `{row['strategy_id']}` | {row['total_r']} | {row['avg_r']} | {row['pf']} | {row['count']} |"
            )
        if not window.get("top_strategy_drags"):
            lines.append("| _none_ | 0 | 0 | 0 | 0 |")
        lines.append("")

        lines.append("### Direction Drags")
        lines.append("")
        lines.append("| Strategy | Direction | Total R | Avg R | PF | Trades |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
        for row in window.get("top_direction_drags", []):
            lines.append(
                f"| `{row['strategy_id']}` | `{row['direction']}` | {row['total_r']} | {row['avg_r']} | {row['pf']} | {row['count']} |"
            )
        if not window.get("top_direction_drags"):
            lines.append("| _none_ | _none_ | 0 | 0 | 0 | 0 |")
        lines.append("")

        lines.append("### Strategy-Year Drags")
        lines.append("")
        lines.append("| Strategy | Year | Total R | Avg R | PF | Trades |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
        for row in window.get("top_strategy_year_drags", []):
            lines.append(
                f"| `{row['strategy_id']}` | `{row['year']}` | {row['total_r']} | {row['avg_r']} | {row['pf']} | {row['count']} |"
            )
        if not window.get("top_strategy_year_drags"):
            lines.append("| _none_ | _none_ | 0 | 0 | 0 | 0 |")
        lines.append("")

        lines.append("### Recommendations")
        lines.append("")
        for item in window.get("recommendations", []):
            lines.append(f"- {item}")
        if not window.get("recommendations"):
            lines.append("- No additional action proposed.")
        lines.append("")

    if payload.get("next_steps"):
        lines.append("## Next Steps")
        lines.append("")
        for item in payload["next_steps"]:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review long-horizon portfolio validation outputs and rank improvement candidates."
    )
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--run-stamp", help="Reconstruct summary payload from existing long_horizon_portfolio evidence")
    parser.add_argument("--validation-log-dir", type=Path, default=DEFAULT_VALIDATION_LOG_DIR)
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--allocation-summary-json", type=Path)
    parser.add_argument("--include-pass", action="store_true")
    parser.add_argument("--top-n", type=int, default=5)
    args = parser.parse_args()

    if args.run_stamp:
        summary_payload = _summary_from_run_stamp(
            run_stamp=args.run_stamp,
            validation_log_dir=args.validation_log_dir,
            analysis_dir=args.analysis_dir,
        )
    else:
        summary_payload = json.loads(args.summary_json.read_text(encoding="utf-8"))
        summary_payload["_source_path"] = str(args.summary_json)
    review = build_review(
        summary_payload,
        failed_only=not args.include_pass,
        top_n=args.top_n,
        allocation_review_payload=args.allocation_summary_json,
    )

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_review_md(review), encoding="utf-8")

    print(json.dumps(review, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
