"""Aggregate execution determinism metrics into a monitoring dashboard."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Mapping

DEFAULT_EXECUTION_LOG = Path("metrics") / "execution_determinism.jsonl"
DEFAULT_DASHBOARD_JSON = Path("reports") / "monitoring" / "execution_dashboard.json"
DEFAULT_DASHBOARD_MD = Path("reports") / "monitoring" / "execution_dashboard.md"
DEFAULT_DASHBOARD_METRICS = Path("metrics") / "execution_dashboard.jsonl"

__all__ = ["execution_dashboard"]


def execution_dashboard(
    *,
    log_path: Path = DEFAULT_EXECUTION_LOG,
    output_path: Path | None = None,
    markdown_path: Path | None = None,
    metrics_path: Path | None = None,
    since: str | None = None,
    window_hours: int | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> Mapping[str, Any]:
    """Aggregate execution determinism metrics for KPI/monitoring use."""

    resolved_output = output_path or DEFAULT_DASHBOARD_JSON
    resolved_markdown = markdown_path or DEFAULT_DASHBOARD_MD
    resolved_metrics = metrics_path or DEFAULT_DASHBOARD_METRICS

    events = _load_jsonl(log_path)
    if limit is not None and limit > 0:
        events = events[-limit:]
    filtered = _filter_events(events, since=since, window_hours=window_hours)
    summary = _aggregate(filtered)
    payload = {
        "status": "ok" if events else "log_missing",
        "log_path": str(log_path),
        "event_count": len(filtered),
        "window": summary.get("window"),
        "summary": summary,
        "output_path": str(resolved_output) if not dry_run else None,
        "markdown_path": str(resolved_markdown) if not dry_run else None,
        "metrics_path": str(resolved_metrics) if not dry_run else None,
    }

    if not dry_run:
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        resolved_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        resolved_markdown.parent.mkdir(parents=True, exist_ok=True)
        resolved_markdown.write_text(_render_markdown(summary), encoding="utf-8")
        _append_metrics(resolved_metrics, summary)
    return payload


def _load_jsonl(path: Path) -> list[Mapping[str, Any]]:
    if not path.exists():
        return []
    events: list[Mapping[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            events.append(payload)
    return events


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except Exception:
            return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _filter_events(
    events: list[Mapping[str, Any]],
    *,
    since: str | None,
    window_hours: int | None,
) -> list[Mapping[str, Any]]:
    if not events:
        return []
    if since is None and window_hours is None:
        return list(events)
    start: datetime | None = _parse_ts(since) if since else None
    if window_hours is not None:
        start = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    filtered: list[Mapping[str, Any]] = []
    for event in events:
        ts = _parse_ts(event.get("ts"))
        if ts is None:
            continue
        if start and ts < start:
            continue
        filtered.append(event)
    return filtered


def _aggregate(events: list[Mapping[str, Any]]) -> dict[str, Any]:
    strategies = {evt.get("strategy_id") for evt in events if evt.get("strategy_id")}
    symbols = {evt.get("symbol") for evt in events if evt.get("symbol")}
    mode_counts = _count_by(events, "mode")
    latency_counts = _count_by(events, "latency_status")
    slippage_counts = _count_by(events, "slippage_status")
    expected = _numeric_values(events, "expected_slippage_pips")
    observed = _numeric_values(events, "observed_slippage_pips")
    rollover = _numeric_values(events, "rollover_pips")
    ttl = _numeric_values(events, "ttl_seconds")
    delay = _numeric_values(events, "human_delay_ms")
    degraded = 0
    for event in events:
        if event.get("latency_status") in {"degraded", "halt_recommended"}:
            degraded += 1
            continue
        if event.get("slippage_status") in {"degraded", "halt_recommended"}:
            degraded += 1
    window = _event_window(events)
    summary = {
        "window": window,
        "unique_strategies": len(strategies),
        "unique_symbols": len(symbols),
        "mode_counts": mode_counts,
        "latency_status_counts": latency_counts,
        "slippage_status_counts": slippage_counts,
        "expected_slippage": _aggregate_stats(expected),
        "observed_slippage": _aggregate_stats(observed),
        "rollover_pips": _aggregate_stats(rollover),
        "ttl_seconds": _aggregate_stats(ttl),
        "human_delay_ms": _aggregate_stats(delay),
        "degraded_ratio": round(degraded / len(events), 4) if events else 0.0,
    }
    return summary


def _event_window(events: list[Mapping[str, Any]]) -> Mapping[str, str | None]:
    timestamps = [_parse_ts(evt.get("ts")) for evt in events]
    valid = [ts for ts in timestamps if ts is not None]
    if not valid:
        return {"since": None, "until": None}
    return {
        "since": min(valid).isoformat(),
        "until": max(valid).isoformat(),
    }


def _count_by(events: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        value = event.get(key) or "unknown"
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _numeric_values(events: list[Mapping[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for event in events:
        raw = event.get(key)
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values


def _aggregate_stats(values: list[float]) -> Mapping[str, float] | None:
    if not values:
        return None
    avg = sum(values) / len(values)
    return {
        "avg": round(avg, 4),
        "p95": round(_percentile(values, 95), 4),
        "max": round(max(values), 4),
        "min": round(min(values), 4),
    }


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (percentile / 100) * (len(ordered) - 1)
    idx = int(math.ceil(rank))
    idx = max(0, min(idx, len(ordered) - 1))
    return float(ordered[idx])


def _render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Execution Determinism Dashboard",
        "",
        f"- Window: {summary.get('window', {}).get('since')} → {summary.get('window', {}).get('until')}",
        f"- Unique strategies: {summary.get('unique_strategies')}",
        f"- Unique symbols: {summary.get('unique_symbols')}",
        f"- Degraded ratio: {summary.get('degraded_ratio')}",
        "",
        "## Status Counts",
        f"- Modes: {summary.get('mode_counts')}",
        f"- Latency: {summary.get('latency_status_counts')}",
        f"- Slippage: {summary.get('slippage_status_counts')}",
        "",
        "## KPI Metrics",
        f"- Expected slippage: {summary.get('expected_slippage')}",
        f"- Observed slippage: {summary.get('observed_slippage')}",
        f"- Rollover pips: {summary.get('rollover_pips')}",
        f"- TTL seconds: {summary.get('ttl_seconds')}",
        f"- Human delay ms: {summary.get('human_delay_ms')}",
        "",
    ]
    return "\n".join(lines)


def _append_metrics(path: Path, summary: Mapping[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "event": "execution.dashboard",
            "ts": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "summary": summary,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
    except OSError:
        return
