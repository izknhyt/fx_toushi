"""Domain JSON schema regression tests (PKG-JSON-SCHEMA-01)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from src.core.schema_registry import build_schema_registry

pytestmark = pytest.mark.json_schema_validation


def _build_validator(
    schema_path: str,
) -> Draft202012Validator:
    schema_file = Path(schema_path)
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    registry = build_schema_registry(schema_file)
    return Draft202012Validator(schema, registry=registry)


def test_accounts_profile_accepts_valid_profile() -> None:
    validator = _build_validator("docs/schemas/accounts_profile.schema.json")
    valid_profile = {
        "schema_version": "accounts.profile.v1",
        "account_id": "acct_primary",
        "broker": "demo_broker",
        "mode": "paper",
        "base_currency": "JPY",
        "weight": 0.35,
        "margin_mode": "netting",
        "max_leverage": 25,
        "is_hedge": False,
        "statement_path": "reports/brokers/demo/{date}.csv",
        "import_schedule_cron": "0 6 * * *",
        "tags": ["ops", "m2"],
        "notes": "Paper account used for pre-production validation.",
    }

    validator.validate(valid_profile)


def test_accounts_profile_rejects_invalid_mode() -> None:
    validator = _build_validator("docs/schemas/accounts_profile.schema.json")
    invalid_profile = {
        "schema_version": "accounts.profile.v1",
        "account_id": "acct_invalid",
        "broker": "demo_broker",
        "mode": "sandbox",
        "base_currency": "USD",
        "weight": 0.5,
        "margin_mode": "netting",
        "max_leverage": 30,
        "is_hedge": True,
        "statement_path": "reports/brokers/demo/{date}.csv",
        "import_schedule_cron": "0 6 * * *",
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid_profile)


def test_order_state_validates_recovery_plan() -> None:
    validator = _build_validator("docs/schemas/order_state.schema.json")
    order_state = {
        "schema_version": "broker.order_state.v1",
        "order_id": "ORD-20250308-001",
        "status": "error",
        "last_transition": "2025-03-08T12:34:56Z",
        "attempt": 2,
        "error_code": "RATE_LIMIT_EXCEEDED",
        "retry_after": 120,
        "ack_received_at": "2025-03-08T12:33:21Z",
        "fill_summary": "shadow-fill-hash",
        "evidence_hash": "abc123def456abc123def456abc123de",
        "recovery_plan": {
            "order_id": "ORD-20250308-001",
            "plan_id": "RP-20250308-001",
            "trigger_reason": "rate_limit",
            "actions": [
                {"code": "wait", "label": "Wait for 120 seconds before retry", "parameters": {"seconds": 120}},
                {"code": "notify_ops", "label": "Notify ops to monitor queue", "requires_manual": True},
            ],
            "assigned_to": "ops_manager",
            "runbook_ref": "RUN-BROKER-API-02#RL-01",
            "status": "planned",
            "created_at": "2025-03-08T12:35:00Z",
            "updated_at": "2025-03-08T12:35:00Z",
            "notes": ["Initial automatic recovery plan created."],
        },
    }

    validator.validate(order_state)


def test_order_state_rejects_unknown_status() -> None:
    validator = _build_validator("docs/schemas/order_state.schema.json")
    invalid_order_state = {
        "schema_version": "broker.order_state.v1",
        "order_id": "ORD-20250308-002",
        "status": "waiting",
        "last_transition": "2025-03-08T12:34:56Z",
        "attempt": 1,
        "evidence_hash": "fff123def456abc123def456abc123de",
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid_order_state)


def test_recovery_plan_rejects_unknown_trigger_reason() -> None:
    validator = _build_validator("docs/schemas/order_state.schema.json")
    invalid_recovery_plan = {
        "order_id": "ORD-20250308-003",
        "plan_id": "RP-20250308-002",
        "trigger_reason": "network_glitch",
        "actions": [{"code": "notify", "label": "Notify team"}],
        "runbook_ref": "RUN-BROKER-API-02#UN-05",
        "status": "planned",
    }

    with pytest.raises(ValidationError):
        validator.validate(
            {
                "schema_version": "broker.order_state.v1",
                "order_id": "ORD-20250308-003",
                "status": "error",
                "last_transition": "2025-03-08T12:00:00Z",
                "attempt": 1,
                "evidence_hash": "abc123def456abc123def456abc123de",
                "recovery_plan": invalid_recovery_plan,
            }
        )


def test_event_resync_completed_accepts_valid_payload() -> None:
    validator = _build_validator("docs/schemas/event_resync_completed.schema.json")
    event = {
        "event": "resync.completed",
        "ts": "2025-03-08T12:45:00Z",
        "source": "core",
        "schema_version": "1.0.0",
        "id": "3f64b198-5f6f-4f34-8fd4-a8f4d3d6d111",
        "correlation_id": "resync.batch.20250308",
        "payload": {
            "catch_up_elapsed_sec": 420,
            "recovered_symbols": ["EURUSD", "USDJPY"],
            "failover_used": ["dukascopy"],
            "manual_csv_required": False,
            "data_hash": "sha256:7f3b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c",
            "cfg_hash": "sha256:2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e",
        },
        "context": {
            "mode": "paper",
            "board_mode": "guarded",
            "cfg_hash": "sha256:2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e",
            "data_hash": "sha256:7f3b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c",
        },
    }

    validator.validate(event)


def test_event_resync_completed_rejects_missing_hash() -> None:
    validator = _build_validator("docs/schemas/event_resync_completed.schema.json")
    invalid = {
        "event": "resync.completed",
        "ts": "2025-03-08T12:45:00Z",
        "source": "core",
        "schema_version": "1.0.0",
        "id": "3f64b198-5f6f-4f34-8fd4-a8f4d3d6d111",
        "payload": {
            "catch_up_elapsed_sec": 420,
            "recovered_symbols": ["EURUSD"],
            "failover_used": [],
            "manual_csv_required": False,
            "cfg_hash": "sha256:2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e",
        },
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid)


def test_audit_ticket_action_accepts_valid_record() -> None:
    validator = _build_validator("docs/schemas/audit_ticket_action.schema.json")
    record = {
        "schema_version": "ticket.action.v2",
        "ts": "2025-03-08T12:50:30Z",
        "record_type": "ticket.action",
        "ticket_id": "TCK-20250308-001",
        "action": "approve",
        "actor": "ops_manager",
        "consent_reference_id": "018f96d8-1c2b-7def-8abc-1a2b3c4d5e6f",
        "board_mode": "guarded",
        "kill_switch_state": "soft_stop",
        "spread_status": "cooldown",
        "profit_readiness_status": "guarded",
        "reduce_only": True,
        "risk_disclosure_state": "pending",
        "auto_execute": False,
        "guardrails": {
            "kill_switch": "soft_stop",
            "spread_status": "cooldown",
            "health_state": "ok",
            "reduce_only": True,
            "reason": "cooldown"
        },
        "cfg_hash": "sha256:9c3dbe9b6f7a21c4d5e68f9a3c7d2e1f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a",
        "data_hash": "sha256:5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c",
        "determinism_hash": "deadbeef",
        "determinism_version": 1,
        "delta": {
            "before": {"status": "pending"},
            "after": {"status": "approved"},
            "diff": {"status": "approved"},
            "decision": "approve",
            "document_hash": "sha256:4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a",
            "consent_version": "2.3.1",
            "expires_at": "2025-06-01T00:00:00Z",
            "ack_user": "risk_lead",
            "ack_evidence": "reports/compliance/ack/2025-03-08.pdf",
        },
        "notes": "Approved after verifying spread cooldown resolved.",
        "extras": {"cli_command": "tradectl ticket approve --id TCK-20250308-001"},
    }

    validator.validate(record)


def test_audit_ticket_action_rejects_missing_delta_fields() -> None:
    validator = _build_validator("docs/schemas/audit_ticket_action.schema.json")
    invalid = {
        "schema_version": "ticket.action.v2",
        "ts": "2025-03-08T12:50:30Z",
        "record_type": "ticket.action",
        "ticket_id": "TCK-20250308-002",
        "action": "reject",
        "actor": "ops_manager",
        "consent_reference_id": None,
        "board_mode": "guarded",
        "guardrails": {
            "kill_switch": "soft_stop",
            "spread_status": "cooldown",
            "health_state": "degraded",
            "reduce_only": False,
        },
        "cfg_hash": "sha256:1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f",
        "data_hash": "sha256:7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c",
        "determinism_hash": None,
        "determinism_version": 1,
        "delta": {
            "before": {"status": "pending"},
            "after": {"status": "rejected"},
            "decision": "reject",
            "consent_version": "2.3.1",
            "expires_at": "2025-06-01T00:00:00Z",
            "ack_user": "ops_manager",
            "ack_evidence": "reports/compliance/ack/2025-03-08.pdf",
        },
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid)


def test_metrics_pipeline_accepts_valid_record() -> None:
    validator = _build_validator("docs/schemas/metrics_pipeline.schema.json")
    record = {
        "ts": "2025-03-08T12:30:00Z",
        "metric": "pipeline_step_elapsed_ms",
        "schema_version": "1.0.0",
        "value": 128.5,
        "labels": {"step": "feature_engineering", "board_mode": "normal"},
    }

    validator.validate(record)


def test_metrics_pipeline_rejects_negative_value() -> None:
    validator = _build_validator("docs/schemas/metrics_pipeline.schema.json")
    invalid = {
        "ts": "2025-03-08T12:30:00Z",
        "metric": "pipeline_step_elapsed_ms",
        "schema_version": "1.0.0",
        "value": -5.0,
        "labels": {"step": "signal_render", "board_mode": "normal"},
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid)


def test_risk_disclosure_state_accepts_valid_state() -> None:
    validator = _build_validator("docs/schemas/risk_disclosure_state.schema.json")
    state = {
        "schema_version": "risk_disclosure_state.v2",
        "status": "accepted",
        "version": "2025.03",
        "document_hash": "sha256:8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8ba1",
        "accepted_at": "2025-03-01T00:00:00Z",
        "expires_at": "2025-06-01T00:00:00Z",
        "ack_user": "ops_manager",
        "ack_source": "cli",
        "consent_reference_id": "018f96d8-1c2b-7def-8abc-1a2b3c4d5e6f",
        "device_fingerprint": "a" * 64,
        "last_prompted_at": "2025-03-01T00:05:00Z",
        "grace_window_hours": 72,
    }

    validator.validate(state)


def test_risk_disclosure_state_rejects_invalid_status() -> None:
    validator = _build_validator("docs/schemas/risk_disclosure_state.schema.json")
    invalid = {
        "schema_version": "risk_disclosure_state.v2",
        "status": "inactive",
        "version": "2025.03",
        "document_hash": "sha256:8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8ba1",
        "grace_window_hours": 72,
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid)


def test_performance_snapshot_sample_is_valid(project_root: Path) -> None:
    validator = _build_validator("docs/schemas/performance_snapshot.schema.json")
    sample_path = project_root / "docs/schemas/examples/performance_snapshot.sample.json"
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    validator.validate(sample)
