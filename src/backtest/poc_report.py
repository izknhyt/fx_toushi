"""PoC analysis report generation utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Iterable, Mapping


def _parse_iso_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _bucket_session(hour: int) -> str:
    if 0 <= hour <= 7:
        return "asia_0_7"
    if 8 <= hour <= 15:
        return "europe_8_15"
    return "us_16_23"


def _bucket_quality(value: float | None) -> str:
    if value is None:
        return "missing"
    if value < 1.0:
        return "lt_1"
    if value < 2.0:
        return "1_2"
    if value < 3.0:
        return "2_3"
    return "ge_3"


def _bucket_trend(value: float | None) -> str:
    if value is None:
        return "missing"
    if value < -0.3:
        return "lt_-0_3"
    if value < 0.0:
        return "-0_3_0"
    if value < 0.3:
        return "0_0_3"
    return "ge_0_3"


def _bucket_ratio(value: float | None) -> str:
    if value is None:
        return "missing"
    if value < 1.0:
        return "lt_1"
    if value < 2.0:
        return "1_2"
    if value < 3.0:
        return "2_3"
    return "ge_3"


def _bucket_atr(value: float | None, q1: float, q2: float) -> str:
    if value is None:
        return "missing"
    if value < q1:
        return "low"
    if value < q2:
        return "mid"
    return "high"


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except Exception:
        return None


@dataclass(frozen=True)
class TradeView:
    opened_at: datetime
    closed_at: datetime
    symbol: str
    direction: str
    entry: float
    exit: float
    stop: float
    target: float
    r_multiple: float
    pnl: float
    strategy_id: str | None = None
    breakout: str | None = None
    breakout_width: float | None = None
    quality_score: float | None = None
    trend_value: float | None = None
    atr_value: float | None = None
    spread_used: float | None = None
    slippage_used: float | None = None

    @property
    def hold_minutes(self) -> float:
        return max((self.closed_at - self.opened_at).total_seconds() / 60.0, 0.0)


def _trade_from_payload(payload: dict[str, Any]) -> TradeView | None:
    opened = _parse_iso_ts(payload.get("opened_at"))
    closed = _parse_iso_ts(payload.get("closed_at"))
    if opened is None or closed is None:
        return None
    direction = payload.get("direction") or "unknown"
    return TradeView(
        opened_at=opened,
        closed_at=closed,
        symbol=payload.get("symbol") or "unknown",
        direction=direction,
        entry=float(payload.get("entry") or 0.0),
        exit=float(payload.get("exit") or 0.0),
        stop=float(payload.get("stop") or 0.0),
        target=float(payload.get("target") or 0.0),
        r_multiple=float(payload.get("r_multiple") or 0.0),
        pnl=float(payload.get("pnl") or 0.0),
        strategy_id=payload.get("strategy_id"),
        breakout=payload.get("breakout"),
        breakout_width=_safe_float(payload.get("breakout_width")),
        quality_score=_safe_float(payload.get("quality_score")),
        trend_value=_safe_float(payload.get("trend_value")),
        atr_value=_safe_float(payload.get("atr_value")),
        spread_used=_safe_float(payload.get("spread_used")),
        slippage_used=_safe_float(payload.get("slippage_used")),
    )


def _group_stats(trades: Iterable[TradeView]) -> dict[str, Any]:
    trades = list(trades)
    if not trades:
        return {
            "count": 0,
            "win_rate": 0.0,
            "avg_r": 0.0,
            "avg_pnl": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "pf": 0.0,
            "avg_hold_min": 0.0,
        }
    wins = [t for t in trades if t.r_multiple > 0]
    losses = [t for t in trades if t.r_multiple <= 0]
    avg_win = mean([t.r_multiple for t in wins]) if wins else 0.0
    avg_loss = mean([t.r_multiple for t in losses]) if losses else 0.0
    pnl_wins = sum(t.pnl for t in wins)
    pnl_losses = sum(t.pnl for t in losses)
    pf = (pnl_wins / abs(pnl_losses)) if pnl_losses else float("inf")
    return {
        "count": len(trades),
        "win_rate": round(len(wins) / len(trades), 4),
        "avg_r": round(mean([t.r_multiple for t in trades]), 4),
        "avg_pnl": round(mean([t.pnl for t in trades]), 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "pf": round(pf, 4) if pf != float("inf") else "inf",
        "avg_hold_min": round(mean([t.hold_minutes for t in trades]), 2),
    }


def _group_by(trades: Iterable[TradeView], key_fn: Callable[[TradeView], str]) -> dict[str, Any]:
    buckets: dict[str, list[TradeView]] = {}
    for trade in trades:
        key = key_fn(trade)
        buckets.setdefault(key, []).append(trade)
    return {key: _group_stats(items) for key, items in sorted(buckets.items())}


def _top_positive_buckets(
    section: Mapping[str, Any], *, min_count: int = 30, limit: int = 3
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for key, stats in section.items():
        if not isinstance(stats, Mapping):
            continue
        count = int(stats.get("count", 0))
        avg_r = float(stats.get("avg_r", 0.0))
        if count < min_count or avg_r <= 0:
            continue
        ranked.append(
            {
                "key": key,
                "count": count,
                "avg_r": avg_r,
                "pf": stats.get("pf"),
                "win_rate": stats.get("win_rate"),
            }
        )
    ranked.sort(key=lambda item: float(item["avg_r"]), reverse=True)
    return ranked[:limit]


def build_poc_report(poc_path: Path) -> dict[str, Any]:
    payload = json.loads(poc_path.read_text(encoding="utf-8"))
    trade_payloads = payload.get("trades", [])
    trades = [t for t in (_trade_from_payload(item) for item in trade_payloads) if t is not None]
    metrics = payload.get("metrics", {})

    atr_values = [t.atr_value for t in trades if t.atr_value is not None]
    atr_values_sorted = sorted(atr_values)
    if atr_values_sorted:
        q1_idx = max(int(len(atr_values_sorted) * 0.33) - 1, 0)
        q2_idx = max(int(len(atr_values_sorted) * 0.66) - 1, 0)
        atr_q1 = atr_values_sorted[q1_idx]
        atr_q2 = atr_values_sorted[q2_idx]
    else:
        atr_q1 = atr_q2 = 0.0

    def _cost_ratio(trade: TradeView) -> float | None:
        cost = (trade.spread_used or 0.0) + (trade.slippage_used or 0.0)
        if cost <= 0:
            return None
        if trade.breakout_width is None:
            return None
        return trade.breakout_width / cost

    report: dict[str, Any] = {
        "source": str(poc_path),
        "metrics": metrics,
        "summary": _group_stats(trades),
        "by_direction": _group_by(trades, lambda t: t.direction or "unknown"),
        "by_year": _group_by(trades, lambda t: str(t.opened_at.year)),
        "by_year_direction": _group_by(trades, lambda t: f"{t.opened_at.year}_{t.direction}"),
        "by_session_utc": _group_by(trades, lambda t: _bucket_session(t.opened_at.hour)),
        "by_weekday": _group_by(trades, lambda t: t.opened_at.strftime("%a")),
        "by_breakout": _group_by(trades, lambda t: t.breakout or "missing"),
        "by_quality": _group_by(trades, lambda t: _bucket_quality(t.quality_score)),
        "by_trend_band": _group_by(trades, lambda t: _bucket_trend(t.trend_value)),
        "by_atr_band": _group_by(
            trades, lambda t: _bucket_atr(t.atr_value, atr_q1, atr_q2)
        ),
        "by_cost_ratio": _group_by(trades, lambda t: _bucket_ratio(_cost_ratio(t))),
        "weak_points": [],
        "atr_quantiles": {"q1": round(atr_q1, 6), "q2": round(atr_q2, 6)},
    }
    summary = report["summary"]
    avg_win = float(summary.get("avg_win", 0.0))
    avg_loss_abs = abs(float(summary.get("avg_loss", 0.0)))
    rr_ratio = (avg_win / avg_loss_abs) if avg_loss_abs > 0 else 0.0
    break_even_win_rate = (1.0 / (1.0 + rr_ratio)) if rr_ratio > 0 else 1.0
    win_rate = float(summary.get("win_rate", 0.0))
    cost_aware_trades = [
        t for t in trades if t.spread_used is not None and t.slippage_used is not None
    ]
    if cost_aware_trades:
        avg_cost_abs = mean(
            [(t.spread_used or 0.0) + (t.slippage_used or 0.0) for t in cost_aware_trades]
        )
        avg_risk_distance = mean(
            [abs(t.entry - t.stop) for t in cost_aware_trades if abs(t.entry - t.stop) > 0]
        )
        avg_cost_r = (avg_cost_abs / avg_risk_distance) if avg_risk_distance > 0 else None
    else:
        avg_cost_abs = 0.0
        avg_cost_r = None
    report["economics"] = {
        "reward_risk_ratio": round(rr_ratio, 4),
        "break_even_win_rate": round(break_even_win_rate, 4),
        "actual_win_rate": round(win_rate, 4),
        "win_rate_edge_vs_break_even": round(win_rate - break_even_win_rate, 4),
        "avg_cost_abs": round(avg_cost_abs, 6),
        "avg_cost_r_estimate": round(avg_cost_r, 4) if avg_cost_r is not None else None,
    }

    def _bucket_streak(count: int) -> str:
        if count == 0:
            return "0"
        if count == 1:
            return "1"
        if count == 2:
            return "2"
        return "3_plus"

    sorted_trades = sorted(trades, key=lambda t: t.opened_at)
    loss_streaks: list[tuple[str, TradeView]] = []
    win_streaks: list[tuple[str, TradeView]] = []
    loss_bucket_map: dict[int, str] = {}
    win_bucket_map: dict[int, str] = {}
    loss_streak = 0
    win_streak = 0
    for trade in sorted_trades:
        loss_bucket = _bucket_streak(loss_streak)
        win_bucket = _bucket_streak(win_streak)
        loss_streaks.append((loss_bucket, trade))
        win_streaks.append((win_bucket, trade))
        loss_bucket_map[id(trade)] = loss_bucket
        win_bucket_map[id(trade)] = win_bucket
        if trade.r_multiple > 0:
            win_streak += 1
            loss_streak = 0
        else:
            loss_streak += 1
            win_streak = 0

    report["by_loss_streak"] = _group_by(
        (t for _, t in loss_streaks), lambda t: loss_bucket_map.get(id(t), "missing")
    )
    report["by_win_streak"] = _group_by(
        (t for _, t in win_streaks), lambda t: win_bucket_map.get(id(t), "missing")
    )

    weak_points: list[dict[str, Any]] = []
    if report["summary"]["avg_r"] < 0:
        weak_points.append(
            {
                "scope": "overall",
                "reason": "negative_expectancy",
                "avg_r": report["summary"]["avg_r"],
                "win_rate": report["summary"]["win_rate"],
            }
        )
    for direction, stats in report["by_direction"].items():
        if stats["avg_r"] < 0 and stats["count"] >= 30:
            weak_points.append(
                {
                    "scope": "direction",
                    "key": direction,
                    "reason": "negative_expectancy",
                    "avg_r": stats["avg_r"],
                    "win_rate": stats["win_rate"],
                    "pf": stats["pf"],
                }
            )
    for year, stats in report["by_year"].items():
        if stats["avg_r"] < 0 and stats["count"] >= 30:
            weak_points.append(
                {
                    "scope": "year",
                    "key": year,
                    "reason": "negative_expectancy",
                    "avg_r": stats["avg_r"],
                    "win_rate": stats["win_rate"],
                    "pf": stats["pf"],
                }
            )
    for bucket, stats in report["by_quality"].items():
        if stats["avg_r"] < 0 and stats["count"] >= 30:
            weak_points.append(
                {
                    "scope": "quality",
                    "key": bucket,
                    "reason": "negative_expectancy",
                    "avg_r": stats["avg_r"],
                    "win_rate": stats["win_rate"],
                    "pf": stats["pf"],
                }
            )
    for bucket, stats in report["by_trend_band"].items():
        if stats["avg_r"] < 0 and stats["count"] >= 30:
            weak_points.append(
                {
                    "scope": "trend_band",
                    "key": bucket,
                    "reason": "negative_expectancy",
                    "avg_r": stats["avg_r"],
                    "win_rate": stats["win_rate"],
                    "pf": stats["pf"],
                }
            )
    for bucket, stats in report["by_atr_band"].items():
        if stats["avg_r"] < 0 and stats["count"] >= 30:
            weak_points.append(
                {
                    "scope": "atr_band",
                    "key": bucket,
                    "reason": "negative_expectancy",
                    "avg_r": stats["avg_r"],
                    "win_rate": stats["win_rate"],
                    "pf": stats["pf"],
                }
            )
    for bucket, stats in report["by_cost_ratio"].items():
        if stats["avg_r"] < 0 and stats["count"] >= 30:
            weak_points.append(
                {
                    "scope": "cost_ratio",
                    "key": bucket,
                    "reason": "negative_expectancy",
                    "avg_r": stats["avg_r"],
                    "win_rate": stats["win_rate"],
                    "pf": stats["pf"],
                }
            )
    report["weak_points"] = weak_points

    year_stats = report["by_year"]
    year_keys = sorted(year_stats.keys())
    positive_years = sum(
        1 for year in year_keys if float(year_stats[year].get("avg_r", 0.0)) > 0
    )
    total_years = len(year_keys)
    positive_year_ratio = (positive_years / total_years) if total_years > 0 else 0.0

    max_drawdown = _safe_float(metrics.get("max_drawdown"))
    acceptance_checks = {
        "avg_r_positive": float(summary.get("avg_r", 0.0)) > 0.0,
        "pf_min_1_10": float(summary.get("pf", 0.0)) >= 1.10,
        "max_dd_le_0_30": (max_drawdown is not None and max_drawdown <= 0.30),
        "year_positive_ratio_ge_0_75": positive_year_ratio >= 0.75,
        "trade_count_ge_300": int(summary.get("count", 0)) >= 300,
    }
    report["acceptance_gate"] = {
        "status": "pass" if all(acceptance_checks.values()) else "fail",
        "checks": acceptance_checks,
        "positive_year_ratio": round(positive_year_ratio, 4),
        "positive_years": positive_years,
        "total_years": total_years,
    }

    report["opportunity_buckets"] = {
        "direction": _top_positive_buckets(report["by_direction"], min_count=30),
        "session_utc": _top_positive_buckets(report["by_session_utc"], min_count=30),
        "atr_band": _top_positive_buckets(report["by_atr_band"], min_count=30),
        "trend_band": _top_positive_buckets(report["by_trend_band"], min_count=30),
        "quality": _top_positive_buckets(report["by_quality"], min_count=30),
        "cost_ratio": _top_positive_buckets(report["by_cost_ratio"], min_count=30),
    }

    next_actions: list[str] = []
    if not acceptance_checks["avg_r_positive"]:
        next_actions.append("Tighten entry filters and reduce low-quality/noise trades.")
    if not acceptance_checks["pf_min_1_10"]:
        next_actions.append("Increase breakout quality threshold and reduce cost-sensitive entries.")
    if not acceptance_checks["max_dd_le_0_30"]:
        next_actions.append("Reduce risk per trade or apply stricter stop/trail policy.")
    if not acceptance_checks["year_positive_ratio_ge_0_75"]:
        next_actions.append("Split strategy by regime/session and disable weak regime buckets.")
    if not acceptance_checks["trade_count_ge_300"]:
        next_actions.append("Increase sample size before deciding production parameters.")
    report["next_actions"] = next_actions
    return report


def render_poc_report_md(report: Mapping[str, Any]) -> str:
    lines = []
    lines.append("# PoC Analysis Report")
    lines.append("")
    lines.append(f"- source: {report.get('source')}")
    lines.append("")
    summary = report.get("summary", {})
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- trades: {summary.get('count')}")
    lines.append(f"- win_rate: {summary.get('win_rate')}")
    lines.append(f"- avg_r: {summary.get('avg_r')}")
    lines.append(f"- pf: {summary.get('pf')}")
    lines.append(f"- avg_hold_min: {summary.get('avg_hold_min')}")
    lines.append("")
    economics = report.get("economics", {})
    lines.append("## Economics")
    lines.append("")
    lines.append(f"- reward_risk_ratio: {economics.get('reward_risk_ratio')}")
    lines.append(f"- break_even_win_rate: {economics.get('break_even_win_rate')}")
    lines.append(f"- actual_win_rate: {economics.get('actual_win_rate')}")
    lines.append(f"- win_rate_edge_vs_break_even: {economics.get('win_rate_edge_vs_break_even')}")
    lines.append(f"- avg_cost_abs: {economics.get('avg_cost_abs')}")
    lines.append(f"- avg_cost_r_estimate: {economics.get('avg_cost_r_estimate')}")
    lines.append("")
    gate = report.get("acceptance_gate", {})
    lines.append("## Acceptance Gate")
    lines.append("")
    lines.append(f"- status: {gate.get('status')}")
    lines.append(f"- positive_year_ratio: {gate.get('positive_year_ratio')}")
    checks = gate.get("checks", {})
    for key, value in checks.items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    def _render_table(title: str, section: Mapping[str, Any]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| key | count | win_rate | avg_r | pf | avg_hold_min |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for key, stats in section.items():
            lines.append(
                f"| {key} | {stats.get('count')} | {stats.get('win_rate')} | {stats.get('avg_r')} | {stats.get('pf')} | {stats.get('avg_hold_min')} |"
            )
        lines.append("")

    _render_table("By Direction", report.get("by_direction", {}))
    _render_table("By Year", report.get("by_year", {}))
    _render_table("By Year + Direction", report.get("by_year_direction", {}))
    _render_table("By Session (UTC)", report.get("by_session_utc", {}))
    _render_table("By Weekday", report.get("by_weekday", {}))
    _render_table("By Breakout", report.get("by_breakout", {}))
    _render_table("By Quality", report.get("by_quality", {}))
    _render_table("By Trend Band", report.get("by_trend_band", {}))
    _render_table("By ATR Band", report.get("by_atr_band", {}))
    _render_table("By Cost Ratio", report.get("by_cost_ratio", {}))
    _render_table("By Loss Streak", report.get("by_loss_streak", {}))
    _render_table("By Win Streak", report.get("by_win_streak", {}))

    weak_points = report.get("weak_points", [])
    lines.append("## Weak Points")
    lines.append("")
    if not weak_points:
        lines.append("- none")
    else:
        for item in weak_points:
            scope = item.get("scope")
            key = item.get("key")
            reason = item.get("reason")
            lines.append(f"- {scope}:{key or 'overall'} => {reason} (avg_r={item.get('avg_r')}, win_rate={item.get('win_rate')}, pf={item.get('pf')})")
    lines.append("")
    lines.append("## Opportunity Buckets")
    lines.append("")
    for section, items in report.get("opportunity_buckets", {}).items():
        lines.append(f"- {section}:")
        if not items:
            lines.append("  - none")
            continue
        for item in items:
            lines.append(
                f"  - {item.get('key')}: avg_r={item.get('avg_r')}, count={item.get('count')}, pf={item.get('pf')}"
            )
    lines.append("")
    lines.append("## Next Actions")
    lines.append("")
    actions = report.get("next_actions", [])
    if not actions:
        lines.append("- none")
    else:
        for action in actions:
            lines.append(f"- {action}")
    lines.append("")
    return "\n".join(lines)
