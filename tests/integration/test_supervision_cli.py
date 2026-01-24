from __future__ import annotations

import json
from pathlib import Path

from src.brokers.stage_guard import AutonomyStageGuard
from src.interfaces.cli.supervision import supervision_status


def test_supervision_status(tmp_path: Path) -> None:
    state_path = tmp_path / "autonomy_state.json"
    audit_path = tmp_path / "autonomy_audit.jsonl"
    readiness_path = tmp_path / "ops_readiness.jsonl"
    broker_audit = tmp_path / "broker_orders.jsonl"
    emergency_log = tmp_path / "emergency_plan.jsonl"
    failover_state = tmp_path / "broker_failover.json"

    readiness_path.write_text(
        json.dumps({"ts": "2026-01-01T00:00:00Z", "readiness_score": 82, "status": "ok"})
        + "\n",
        encoding="utf-8",
    )
    guard = AutonomyStageGuard(state_path=state_path, audit_log_path=audit_path)
    guard.request_transition("reduce_only", actor="ops", reason="smoke")

    payload = supervision_status(
        autonomy_state_path=state_path,
        autonomy_audit_path=audit_path,
        broker_audit_path=broker_audit,
        emergency_log_path=emergency_log,
        failover_state_path=failover_state,
        readiness_metrics_path=readiness_path,
    )

    assert payload["status"] == "ok"
    assert payload["autonomy_stage"]["stage"] == "manual_only"
    assert payload["pending_requests"]
