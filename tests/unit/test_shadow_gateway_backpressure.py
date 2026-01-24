from __future__ import annotations

import json
from pathlib import Path

from src.shadow_gateway.audit import AuditSink
from src.shadow_gateway.backpressure import BackpressureGovernor
from src.shadow_gateway.metrics import GatewayMetrics


def test_shadow_gateway_backpressure_threshold(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.jsonl"
    audit_path = tmp_path / "audit.jsonl"
    governor = BackpressureGovernor(
        metrics=GatewayMetrics(path=metrics_path),
        audit=AuditSink(path=audit_path),
    )

    state = governor.observe(queue_depth=80, capacity=100, session_id="sess-1", channel="sse")
    assert state == "throttled"

    last_entry = json.loads(metrics_path.read_text(encoding="utf-8").splitlines()[-1])
    assert last_entry["backpressure_state"] == "throttled"
    assert last_entry["queue_depth"] == 80
    assert last_entry["queue_depth_ratio"] == 0.8
