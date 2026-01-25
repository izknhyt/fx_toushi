from __future__ import annotations

import json
from pathlib import Path

from tools.shadow_gateway.aggregate import aggregate


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_shadow_gateway_aggregate_summary(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.jsonl"
    audit_path = tmp_path / "audit.jsonl"
    _write_jsonl(
        metrics_path,
        [
            {"metric": "shadow.gateway.reconnect_time", "value": 10, "latency_ms": None},
            {"metric": "shadow.gateway.reconnect_time", "value": 20, "latency_ms": None},
            {"metric": "shadow.gateway.cache_replay_success", "value": 1.0},
            {"metric": "shadow.gateway.command.retry", "value": 1, "latency_ms": 100},
            {"metric": "shadow.gateway.command.retry", "value": 1, "latency_ms": 400},
        ],
    )
    _write_jsonl(
        audit_path,
        [
            {
                "event_type": "audit.shadow_gateway.session",
                "ts": "2026-01-24T00:00:00Z",
                "payload": {"state": "active", "reason": "started"},
            },
            {
                "event_type": "audit.shadow_gateway.session",
                "ts": "2026-01-24T00:10:00Z",
                "payload": {"state": "disabled", "reason": "feature_flag_disabled"},
            },
            {
                "event_type": "audit.shadow_gateway.session",
                "ts": "2026-01-24T00:20:00Z",
                "payload": {"state": "active", "reason": "started"},
            },
        ],
    )
    summary = aggregate(metrics_path=metrics_path, audit_path=audit_path)
    assert summary.availability == 0.5
    assert summary.latency_p95 == 400
    assert summary.reconnect_time_p95 == 20
    assert summary.cache_replay_success == 1.0
