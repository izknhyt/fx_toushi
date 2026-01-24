from __future__ import annotations

import json
from pathlib import Path

import json

from src.shadow_gateway.audit import AuditSink
from src.shadow_gateway.feature_flag import ShadowGatewayFeature
from src.shadow_gateway.metrics import GatewayMetrics
from src.shadow_gateway.session_supervisor import SessionSupervisor


def _write_flags(path: Path, *, mode: str, streaming: bool, force_failover: bool = False) -> None:
    payload = {
        "schema_version": "feature_flags.v1",
        "defaults": {
            mode: {
                "shadow.gateway.streaming": streaming,
                "shadow.gateway.force_failover": force_failover,
            }
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_shadow_gateway_session_reconnect_and_audit(tmp_path: Path) -> None:
    flags_path = tmp_path / "feature_flags.yaml"
    _write_flags(flags_path, mode="paper", streaming=True)
    metrics_path = tmp_path / "metrics.jsonl"
    audit_path = tmp_path / "audit.jsonl"

    supervisor = SessionSupervisor(
        metrics=GatewayMetrics(path=metrics_path),
        audit=AuditSink(path=audit_path),
        feature_flags=ShadowGatewayFeature(path=flags_path),
    )
    session = supervisor.start(
        primary_endpoint="https://primary",
        secondary_endpoint="https://secondary",
        profile="paper",
    )
    supervisor.record_event(1)
    supervisor.record_event(2)
    assert session.connected is True
    assert session.last_event_id == 2

    reconnect = supervisor.handle_disconnect("network_lost")
    assert reconnect["status"] == "ok"
    assert reconnect["reconnect_seconds"] <= 30

    audit_lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert any(
        json.loads(line).get("event_type") == "audit.shadow_gateway.retry" for line in audit_lines
    )
