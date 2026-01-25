"""Aggregate Shadow Gateway telemetry into summary metrics."""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from src.shadow_gateway.metrics import GatewayMetrics


@dataclass(slots=True)
class GatewayAggregate:
    availability: float | None
    latency_p95: float | None
    reconnect_time_p95: float | None
    cache_replay_success: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "availability": self.availability,
            "latency_p95": self.latency_p95,
            "reconnect_time_p95": self.reconnect_time_p95,
            "cache_replay_success": self.cache_replay_success,
        }


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    k = max(0, min(len(values) - 1, int(round((pct / 100.0) * (len(values) - 1)))))  # type: ignore[arg-type]
    return values[k]


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records


def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _state_from_payload(payload: dict[str, object]) -> str | None:
    state = payload.get("state")
    if isinstance(state, str):
        return state
    reason = str(payload.get("reason") or "")
    if "feature_flag_disabled" in reason:
        return "disabled"
    return None


def _compute_availability(audit_path: Path) -> float | None:
    sessions = [
        r
        for r in _load_jsonl(audit_path)
        if r.get("event_type") == "audit.shadow_gateway.session"
    ]
    if not sessions:
        return None
    timeline = []
    for entry in sessions:
        ts = _parse_ts(entry.get("ts"))
        payload = entry.get("payload") or {}
        if isinstance(payload, dict):
            state = _state_from_payload(payload)
        else:
            state = None
        if ts and state:
            timeline.append((ts, state))
    if len(timeline) < 2:
        # fallback to event ratio
        active = sum(1 for _, state in timeline if state in {"active", "failover"})
        disabled = sum(1 for _, state in timeline if state == "disabled")
        total = active + disabled
        return (active / total) if total else None
    timeline.sort(key=lambda item: item[0])
    up_seconds = 0.0
    total_seconds = 0.0
    last_ts, last_state = timeline[0]
    for ts, state in timeline[1:]:
        delta = (ts - last_ts).total_seconds()
        if delta > 0:
            total_seconds += delta
            if last_state in {"active", "failover"}:
                up_seconds += delta
        last_ts = ts
        last_state = state
    if total_seconds <= 0:
        return None
    return up_seconds / total_seconds


def _compute_cache_success(metrics_path: Path) -> float | None:
    values = [
        float(r.get("value"))
        for r in _load_jsonl(metrics_path)
        if r.get("metric") == "shadow.gateway.cache_replay_success"
    ]
    if not values:
        return None
    try:
        return statistics.mean(values)
    except statistics.StatisticsError:
        return None


def aggregate(
    *,
    metrics_path: Path,
    audit_path: Path,
) -> GatewayAggregate:
    metrics = list(_load_jsonl(metrics_path))
    latencies = [
        float(r.get("latency_ms"))
        for r in metrics
        if r.get("latency_ms") is not None
    ]
    reconnects = [
        float(r.get("value"))
        for r in metrics
        if r.get("metric") == "shadow.gateway.reconnect_time"
    ]
    availability = _compute_availability(audit_path)
    return GatewayAggregate(
        availability=availability,
        latency_p95=_percentile(latencies, 95),
        reconnect_time_p95=_percentile(reconnects, 95),
        cache_replay_success=_compute_cache_success(metrics_path),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", default="metrics/shadow_gateway.jsonl", help="Metrics path")
    parser.add_argument("--audit", default="logs/audit/shadow_gateway.jsonl", help="Audit path")
    parser.add_argument("--out", default="metrics/shadow_gateway_summary.jsonl", help="Output path")
    args = parser.parse_args()

    metrics_path = Path(args.metrics)
    audit_path = Path(args.audit)
    output_path = Path(args.out)

    summary = aggregate(metrics_path=metrics_path, audit_path=audit_path)
    writer = GatewayMetrics(path=output_path)
    payload = summary.to_dict()
    if summary.availability is not None:
        writer.record("shadow.gateway.availability", summary.availability)
    if summary.latency_p95 is not None:
        writer.record("shadow.gateway.latency_p95", summary.latency_p95)
    if summary.reconnect_time_p95 is not None:
        writer.record("shadow.gateway.reconnect_time_p95", summary.reconnect_time_p95)
    if summary.cache_replay_success is not None:
        writer.record("shadow.gateway.cache_replay_success_rate", summary.cache_replay_success)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "summary": payload, "output_path": str(output_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
