"""Aggregate Shadow Gateway telemetry into summary metrics."""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
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


def _compute_availability(audit_path: Path) -> float | None:
    sessions = [r for r in _load_jsonl(audit_path) if r.get("event_type") == "audit.shadow_gateway.session"]
    if not sessions:
        return None
    active = 0
    disabled = 0
    for entry in sessions:
        payload = entry.get("payload") or {}
        state = payload.get("state")
        reason = str(payload.get("reason") or "")
        if state in {"active", "failover"}:
            active += 1
        if state == "disabled" or "feature_flag_disabled" in reason:
            disabled += 1
    total = active + disabled
    if total == 0:
        return None
    return active / total


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
