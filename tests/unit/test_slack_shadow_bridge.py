from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.shadow.slack_bridge import ShadowChannelConfig, ShadowPayload, SlackShadowBridge


def _write_feature_flags(path: Path, enabled: bool) -> None:
    content = "\n".join(
        [
            "schema_version: feature_flags.v1",
            "defaults:",
            "  live:",
            f"    shadow.slack_enabled: {'true' if enabled else 'false'}",
        ]
    )
    path.write_text(content + "\n", encoding="utf-8")


def _payload(event_type: str = "ticket.proposed") -> ShadowPayload:
    return ShadowPayload(
        event_type=event_type,
        ticket_id="T-1",
        title="Test",
        body_md="body",
        badges=["shadow"],
        risk_state="ok",
        board_mode="normal",
        health_state="ok",
        consent_reference_id=None,
        runbook_link="RUN-SHADOW-01",
        actions=[],
    )


def test_publish_respects_feature_flag(tmp_path: Path, monkeypatch: object) -> None:
    flags = tmp_path / "feature_flags.yaml"
    _write_feature_flags(flags, enabled=False)
    monkeypatch.setenv("TRADECTL_PROFILE", "live")

    message_log = tmp_path / "logs" / "shadow" / "slack_messages.jsonl"
    bridge = SlackShadowBridge(feature_flags_path=flags, message_log=message_log)
    result = bridge.publish(_payload(), channel_config=ShadowChannelConfig(channel_id="C1"))

    assert result["status"] == "skipped"
    assert not message_log.exists()


def test_publish_filters_severity(tmp_path: Path, monkeypatch: object) -> None:
    flags = tmp_path / "feature_flags.yaml"
    _write_feature_flags(flags, enabled=True)
    monkeypatch.setenv("TRADECTL_PROFILE", "live")

    message_log = tmp_path / "logs" / "shadow" / "slack_messages.jsonl"
    bridge = SlackShadowBridge(feature_flags_path=flags, message_log=message_log)
    config = ShadowChannelConfig(channel_id="C1", severity_filter="critical")
    result = bridge.publish(_payload(event_type="alert.warning"), channel_config=config)

    assert result["status"] == "skipped"
    assert result["reason"] == "severity_filtered"
    assert not message_log.exists()


def test_interaction_logs_audit_and_metrics(tmp_path: Path, monkeypatch: object) -> None:
    flags = tmp_path / "feature_flags.yaml"
    _write_feature_flags(flags, enabled=True)
    monkeypatch.setenv("TRADECTL_PROFILE", "live")

    audit_log = tmp_path / "logs" / "audit" / "shadow_interactions.jsonl"
    metrics_log = tmp_path / "metrics" / "shadow_bridge.jsonl"
    worklog_path = tmp_path / "ops_worklog.jsonl"
    bridge = SlackShadowBridge(
        feature_flags_path=flags,
        audit_log=audit_log,
        metrics_path=metrics_log,
        ops_worklog_path=worklog_path,
    )

    payload = {"ticket_id": "T-9", "actor": "ops", "note": "ack"}
    result = bridge.handle_interaction(payload)

    assert result["status"] == "ok"
    assert audit_log.exists()
    assert worklog_path.exists()
    audit_payload = json.loads(audit_log.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_payload["ticket_id"] == "T-9"
    metrics_payload = json.loads(metrics_log.read_text(encoding="utf-8").splitlines()[-1])
    assert metrics_payload["event"] == "shadow.interaction.recorded"


def test_sync_threads_records_message(tmp_path: Path, monkeypatch: object) -> None:
    flags = tmp_path / "feature_flags.yaml"
    _write_feature_flags(flags, enabled=True)
    monkeypatch.setenv("TRADECTL_PROFILE", "live")

    message_log = tmp_path / "logs" / "shadow" / "slack_messages.jsonl"
    bridge = SlackShadowBridge(feature_flags_path=flags, message_log=message_log)
    result = bridge.sync_threads(ticket_id="T-4", channel_id="C9")

    assert result["status"] == "ok"
    assert message_log.exists()
