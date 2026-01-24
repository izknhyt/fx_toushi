from __future__ import annotations

from pathlib import Path

import json

from src.shadow_gateway.audit import AuditSink
from src.shadow_gateway.feature_flag import ShadowGatewayFeature
from src.shadow_gateway.metrics import GatewayMetrics
from src.shadow_gateway.session_supervisor import SessionSupervisor


def _write_flags(path: Path, *, mode: str, streaming: bool) -> None:
    payload = {
        "schema_version": "feature_flags.v1",
        "defaults": {mode: {"shadow.gateway.streaming": streaming}},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_shadow_gateway_feature_flag_disables_session(tmp_path: Path) -> None:
    flags_path = tmp_path / "feature_flags.yaml"
    _write_flags(flags_path, mode="live", streaming=False)
    supervisor = SessionSupervisor(
        metrics=GatewayMetrics(path=tmp_path / "metrics.jsonl"),
        audit=AuditSink(path=tmp_path / "audit.jsonl"),
        feature_flags=ShadowGatewayFeature(path=flags_path),
    )
    session = supervisor.start(
        primary_endpoint="https://primary",
        secondary_endpoint="https://secondary",
        profile="live",
    )
    assert session.state == "disabled"
    assert session.connected is False


def test_shadow_gateway_retry_within_three_attempts(tmp_path: Path) -> None:
    flags_path = tmp_path / "feature_flags.yaml"
    _write_flags(flags_path, mode="paper", streaming=True)
    supervisor = SessionSupervisor(
        metrics=GatewayMetrics(path=tmp_path / "metrics.jsonl"),
        audit=AuditSink(path=tmp_path / "audit.jsonl"),
        feature_flags=ShadowGatewayFeature(path=flags_path),
    )
    supervisor.start(
        primary_endpoint="https://primary",
        secondary_endpoint="https://secondary",
        profile="paper",
    )
    attempts = {"count": 0}

    def flaky_command() -> bool:
        attempts["count"] += 1
        return attempts["count"] >= 3

    result = supervisor.execute_with_retry(flaky_command)
    assert result["status"] == "ok"
    assert result["attempts"] <= 3
