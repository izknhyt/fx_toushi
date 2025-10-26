from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

pytestmark = pytest.mark.smoke


def test_accounts_profile_accepts_valid_profile(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    schema = load_json_schema("schema/accounts_profile.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

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


def test_accounts_profile_rejects_invalid_mode(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    schema = load_json_schema("schema/accounts_profile.schema.json")
    validator = Draft202012Validator(schema)

    invalid_profile = {
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


def test_order_state_validates_recovery_plan(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    schema = load_json_schema("schema/order_state.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

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
                {
                    "code": "wait",
                    "label": "Wait for 120 seconds before retry",
                    "parameters": {"seconds": 120},
                },
                {
                    "code": "notify_ops",
                    "label": "Notify ops to monitor queue",
                    "requires_manual": True,
                },
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


def test_order_state_rejects_unknown_status(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    schema = load_json_schema("schema/order_state.schema.json")
    validator = Draft202012Validator(schema)

    invalid_order_state = {
        "order_id": "ORD-20250308-002",
        "status": "waiting",
        "last_transition": "2025-03-08T12:34:56Z",
        "attempt": 1,
        "evidence_hash": "fff123def456abc123def456abc123de",
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid_order_state)


def test_recovery_plan_rejects_unknown_trigger_reason(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    schema = load_json_schema("schema/order_state.schema.json")
    validator = Draft202012Validator(schema)

    invalid_recovery_plan = {
        "order_id": "ORD-20250308-003",
        "plan_id": "RP-20250308-002",
        "trigger_reason": "network_glitch",
        "actions": [
            {"code": "notify", "label": "Notify team"}
        ],
        "runbook_ref": "RUN-BROKER-API-02#UN-05",
        "status": "planned",
    }

    with pytest.raises(ValidationError):
        validator.validate(
            {
                "order_id": "ORD-20250308-003",
                "status": "error",
                "last_transition": "2025-03-08T12:00:00Z",
                "attempt": 1,
                "evidence_hash": "abc123def456abc123def456abc123de",
                "recovery_plan": invalid_recovery_plan,
            }
        )
