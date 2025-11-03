from __future__ import annotations

import json
import warnings
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=".*RefResolver is deprecated.*",
)

from jsonschema.validators import RefResolver

pytestmark = pytest.mark.smoke


def _build_validator(
    load_json_schema: Callable[[str | Path], dict],
    schema_path: str,
) -> Draft202012Validator:
    schema_file = Path(schema_path)
    schema = load_json_schema(schema_path)
    Draft202012Validator.check_schema(schema)
    base_uri = schema_file.resolve().as_uri()

    store: dict[str, Any] = {}
    for candidate in schema_file.parent.glob("*.schema.json"):
        try:
            candidate_data = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        schema_id = candidate_data.get("$id")
        if schema_id:
            store[schema_id] = candidate_data
        fallback_id = f"https://fx-toushi.dev/schemas/{candidate.name}"
        store.setdefault(fallback_id, candidate_data)
        store.setdefault(candidate.resolve().as_uri(), candidate_data)

    resolver = RefResolver(base_uri=base_uri, referrer=schema)
    resolver.store.update(store)
    return Draft202012Validator(schema, resolver=resolver)


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


def test_resync_completed_event_accepts_valid_payload(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/event_resync_completed.schema.json"
    )

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


def test_resync_completed_event_rejects_missing_hash(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/event_resync_completed.schema.json"
    )

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


def test_audit_ticket_action_accepts_valid_record(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/audit_ticket_action.schema.json"
    )

    record = {
        "schema_version": "ticket.action.v1",
        "ts": "2025-03-08T12:50:30Z",
        "record_type": "ticket.action",
        "ticket_id": "TCK-20250308-001",
        "action": "approve",
        "actor": "ops_manager",
        "consent_reference_id": "018f96d8-1c2b-7def-8abc-1a2b3c4d5e6f",
        "board_mode": "guarded",
        "spread_state": {
            "EURUSD": {
                "state": "normal",
                "spread_pips": 0.6,
                "percentile": 0.42,
                "threshold_pips": 1.2,
                "cooldown_eta": None,
                "last_updated": "2025-03-08T12:50:00Z",
                "lookback_window_sec": 900,
                "reason": None,
            }
        },
        "health_state": "degraded",
        "cfg_hash": "sha256:9c3dbe9b6f7a21c4d5e68f9a3c7d2e1f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a",
        "data_hash": "sha256:5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c",
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


def test_audit_ticket_action_rejects_missing_delta_fields(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/audit_ticket_action.schema.json"
    )

    invalid = {
        "ts": "2025-03-08T12:50:30Z",
        "record_type": "ticket.action",
        "ticket_id": "TCK-20250308-002",
        "action": "reject",
        "actor": "ops_manager",
        "board_mode": "guarded",
        "spread_state": {
            "USDJPY": {
                "state": "watch",
                "spread_pips": 1.4,
                "percentile": 0.78,
                "threshold_pips": 1.5,
                "cooldown_eta": "2025-03-08T13:00:00Z",
                "last_updated": "2025-03-08T12:48:00Z",
                "lookback_window_sec": 900,
            }
        },
        "health_state": "degraded",
        "cfg_hash": "sha256:1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f",
        "data_hash": "sha256:7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c",
        "delta": {
            "before": {"status": "pending"},
            "after": {"status": "rejected"},
            "diff": {"status": "rejected"},
            "decision": "reject",
            "consent_version": "2.3.1",
            "expires_at": "2025-06-01T00:00:00Z",
            "ack_user": "ops_manager",
            "ack_evidence": "reports/compliance/ack/2025-03-08.pdf",
        },
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid)


def test_metrics_pipeline_accepts_valid_record(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/metrics_pipeline.schema.json"
    )

    record = {
        "ts": "2025-03-08T12:30:00Z",
        "metric": "pipeline_step_elapsed_ms",
        "schema_version": "1.0.0",
        "value": 128.5,
        "labels": {"step": "feature_engineering", "board_mode": "normal"},
    }

    validator.validate(record)


def test_metrics_pipeline_rejects_negative_value(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/metrics_pipeline.schema.json"
    )

    invalid = {
        "ts": "2025-03-08T12:30:00Z",
        "metric": "pipeline_step_elapsed_ms",
        "schema_version": "1.0.0",
        "value": -5.0,
        "labels": {"step": "signal_render", "board_mode": "normal"},
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid)


def test_risk_disclosure_state_accepts_valid_state(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/risk_disclosure_state.schema.json"
    )

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


def test_risk_disclosure_state_rejects_invalid_status(
    load_json_schema: Callable[[str | Path], dict],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/risk_disclosure_state.schema.json"
    )

    invalid = {
        "schema_version": "risk_disclosure_state.v2",
        "status": "inactive",
        "version": "2025.03",
        "document_hash": "sha256:8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8b9d3a0e5f6b8c4d2a1e6f7c8ba1",
        "grace_window_hours": 72,
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid)


@pytest.mark.config_schema_smoke
def test_strategy_manifest_scaffold_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/strategy_manifest.schema.json"
    )
    manifest = load_config("config/strategy_manifest.yaml")

    validator.validate(manifest)


@pytest.mark.config_schema_smoke
def test_feature_pipeline_scaffold_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/feature_pipeline.schema.json"
    )
    pipeline_cfg = load_config("config/feature_pipeline.yaml")

    validator.validate(pipeline_cfg)


@pytest.mark.config_schema_smoke
def test_board_modes_scaffold_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/board_modes.schema.json"
    )
    board_modes = load_config("config/board_modes.yaml")

    validator.validate(board_modes)


@pytest.mark.config_schema_smoke
def test_execution_model_scaffold_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/execution_model.schema.json"
    )
    execution_model = load_config("config/execution_model.yaml")

    validator.validate(execution_model)


@pytest.mark.config_schema_smoke
def test_feature_flags_config_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/feature_flags.schema.json"
    )
    feature_flags = load_config("config/feature_flags.yaml")

    validator.validate(feature_flags)


@pytest.mark.config_schema_smoke
def test_ops_config_scaffold_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/ops_config.schema.json"
    )
    ops_config = load_config("config/ops.yaml")

    validator.validate(ops_config)


@pytest.mark.config_schema_smoke
def test_ops_readiness_scaffold_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/ops_readiness.schema.json"
    )
    ops_readiness = load_config("config/ops_readiness.yaml")

    validator.validate(ops_readiness)


@pytest.mark.config_schema_smoke
def test_roles_config_scaffold_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/roles_config.schema.json"
    )
    roles_config = load_config("config/roles.yaml")

    validator.validate(roles_config)


@pytest.mark.config_schema_smoke
def test_broker_rules_config_matches_schema(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/broker_rules.schema.json"
    )
    broker_rules = load_config("config/broker_rules.yaml")

    validator.validate(broker_rules)


@pytest.mark.config_schema_smoke
def test_scoring_config_scaffold_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/scoring_config.schema.json"
    )
    scoring_config = load_config("config/scoring.yaml")

    validator.validate(scoring_config)


@pytest.mark.config_schema_smoke
def test_scoreboard_config_scaffold_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/scoreboard.schema.json"
    )
    scoreboard_config = load_config("config/scoreboard.yaml")

    validator.validate(scoreboard_config)


@pytest.mark.config_schema_smoke
def test_risk_live_guard_scaffold_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/risk_live_guard.schema.json"
    )
    risk_live_guard = load_config("config/risk_live_guard.yaml")

    validator.validate(risk_live_guard)


@pytest.mark.config_schema_smoke
@pytest.mark.parametrize(
    "profile_name",
    ["backtest", "paper", "live"],
)
def test_profiles_match_cfg_schema(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
    profile_name: str,
) -> None:
    validator = _build_validator(load_json_schema, "docs/schemas/cfg.schema.json")
    profile = load_config(f"config/profiles/{profile_name}.yaml")

    validator.validate(profile)


@pytest.mark.config_schema_smoke
@pytest.mark.parametrize(
    "profile_path",
    [
        "config/sla_thresholds/default.yaml",
        "config/sla_thresholds/active.yaml",
    ],
)
def test_sla_threshold_profiles_are_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
    profile_path: str,
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/sla_threshold_profile.schema.json"
    )
    profile = load_config(profile_path)

    validator.validate(profile)


@pytest.mark.config_schema_smoke
def test_config_bundle_schema_covers_scaffolds(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
    project_root: Path,
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/config_bundle.schema.json"
    )
    config_dir = project_root / "config"

    bundle: dict[str, object] = {}
    for path in sorted(config_dir.rglob("*")):
        if path.is_dir():
            continue
        if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        relative = path.relative_to(config_dir).as_posix()
        bundle[relative] = load_config(Path("config") / Path(relative))

    validator.validate(bundle)


@pytest.mark.config_schema_smoke
def test_gate_state_sample_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(load_json_schema, "docs/schemas/gate_state.schema.json")
    gate_state = load_config("schema/gate_state.sample.json")

    validator.validate(gate_state)


def test_gate_state_symbol_specific_spread_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(load_json_schema, "docs/schemas/gate_state.schema.json")
    gate_state = load_config("schema/gate_state.sample.json")
    gate_state_with_symbol_spread = deepcopy(gate_state)

    gate_state_with_symbol_spread["market"]["per_symbol"]["EURUSD"] = {
        "spread": {
            "state": "halt",
            "reason": "broker_quote_missing",
            "cooldown_eta": "2025-03-14T12:50:00Z",
        }
    }

    validator.validate(gate_state_with_symbol_spread)


def test_gate_state_symbol_without_spread_slice_is_valid(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    validator = _build_validator(load_json_schema, "docs/schemas/gate_state.schema.json")
    gate_state = load_config("schema/gate_state.sample.json")
    gate_state_without_spread_slice = deepcopy(gate_state)

    gate_state_without_spread_slice["market"]["per_symbol"]["EURUSD"] = {
        "news": {
            "blocked": True,
            "reason": "eurusd_data_lag",
            "release_ts": "2025-03-14T12:35:00Z",
        }
    }

    validator.validate(gate_state_without_spread_slice)


def _sample_mode_context_payload() -> dict[str, Any]:
    return {
        "schema_version": "mode.context.v1",
        "mode": "paper",
        "profile": {
            "schema_version": 1,
            "profile_id": "paper",
            "mode": "paper",
            "metadata": {
                "description": "Paper trading profile",
                "runbook_refs": ["docs/runbooks/RUN-PERF-01.md"],
                "tags": ["mode=paper", "release=m1"]
            },
            "data_ingestion": {
                "provider": "yfinance",
                "symbols": ["USDJPY", "EURUSD"],
                "catch_up_enabled": True,
                "manual_fallback_allowed": True
            },
            "timeframes": {
                "trigger": "5m",
                "regime_ref": "1h"
            },
            "risk": {
                "policy_id": "m1_baseline",
                "overrides": {}
            },
            "gates": {
                "board_mode_default": "normal",
                "enable_news_block": True,
                "required_roles": [
                    "primary_operator",
                    "risk_officer"
                ],
                "comment_min_length": 12,
                "comment_max_length": 320
            },
            "strategies": [
                {
                    "id": "m1_baseline_ma_rsi",
                    "enabled": True,
                    "weight": 1.0
                }
            ],
            "execution": {
                "slippage_bps": 1.5,
                "latency_simulation_ms": 250,
                "human_delay_secs": 12
            },
            "spread": {
                "source": "live_feed",
                "cooldown_minutes": 15
            },
            "funding": {
                "apply_swap": True
            },
            "correlation": {
                "dataset": "data/correlation/paper/latest.parquet"
            },
            "scheduler": {
                "timezone": "UTC",
                "session_start": "00:00",
                "session_end": "23:55"
            }
        },
        "clock": {
            "name": "UtcMarketClock",
            "timezone": "UTC",
            "timeframe": "5m",
            "trading_calendar": {
                "id": "global_fx",
                "region": "UTC",
                "holidays": ["2025-01-01"]
            },
            "supports_halt_windows": True,
            "sync_source": "ntp.pool.org",
            "drift_tolerance_ms": 500,
            "bar_alignment": {
                "interval_seconds": 300,
                "phase_offset_seconds": 0
            }
        },
        "deterministic_seed": 123456,
        "data_feeds": {
            "primary": {
                "provider": "yfinance",
                "channel": "rest",
                "credentials_ref": "secret/yfinance"
            },
            "fallback": [
                {
                    "provider": "dukascopy",
                    "channel": "rest"
                }
            ],
            "manual_sources": [
                {
                    "template_path": "data/manual_fallback/yfinance/USDJPY",
                    "runbook_ref": "RUN-DATA-06"
                }
            ],
            "ingestion_parallelism": 4,
            "quality_guards": {
                "max_gap_minutes": 10,
                "stale_bar_threshold_minutes": 8
            },
            "rate_limit_guard": {
                "stage": "baseline"
            }
        },
        "execution_profile": {
            "model_id": "execution.baseline.v1",
            "allowed_entry_modes": [
                "market",
                "marketable_limit",
                "limit_requote"
            ],
            "human_delay_secs": 12,
            "latency_distribution_ms": {
                "p50": 120,
                "p95": 250,
                "p99": 400
            },
            "slippage_bps": 1.5,
            "max_orders_per_minute": 6,
            "kill_switch_policies": {
                "reduce_only_on_soft_stop": True,
                "require_double_ack": True
            },
            "staging": {
                "paper": {
                    "stage_guard": "manual_only"
                }
            }
        },
        "account_gateway": {
            "type": "paper_simulator",
            "account_profile_id": "acct_paper_primary",
            "statement_export": {
                "path_glob": "reports/brokers/paper/*.csv",
                "frequency": "daily"
            },
            "balance_source": "simulated",
            "supports_margin": True,
            "supports_swap": True,
            "latency_budget_ms": 150,
            "risk_buffer_pct": 0.05
        },
        "audit_channel": {
            "stream": "audit.mode.paper",
            "writer": {
                "path": "logs/audit/paper.jsonl",
                "append_mode": "jsonl"
            },
            "retention_days": 30,
            "sync_targets": ["s3://audit-paper"],
            "encryption": {
                "enabled": True,
                "key_alias": "alias/audit"
            },
            "redaction_policy": "default",
            "evidence_tags": ["mode=paper", "region=apac"]
        },
        "session_state": {
            "mode": "paper",
            "health": "ok",
            "board_mode": "normal",
            "kill_switch": "RUNNING",
            "active_jobs": ["backfill:USDJPY:5m"],
            "cfg_hash": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "last_bar_ts": "2025-03-18T10:15:00Z",
            "last_resync_at": "2025-03-18T10:20:00Z",
            "snapshot_version": "snapshot.state.v1"
        },
        "session_handle": {
            "session_id": "session-20250318-0001",
            "profile_id": "paper",
            "mode": "paper",
            "started_at": "2025-03-18T09:59:00Z",
            "cfg_hash": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "clock_snapshot_ts": "2025-03-18T10:15:00Z",
            "event_stream_id": "ops.session.paper.20250318"
        },
        "active_backfill_jobs": [
            {
                "job_id": "bf-20250318-01",
                "mode": "paper",
                "symbols": ["USDJPY"],
                "timeframe": "5m",
                "start_ts": "2025-03-18T06:00:00Z",
                "end_ts": "2025-03-18T09:55:00Z",
                "priority": "critical",
                "provider": "yfinance",
                "status": "running",
                "retry_count": 0,
                "requested_by": "session_manager",
                "created_at": "2025-03-18T10:00:00Z",
                "last_heartbeat": "2025-03-18T10:14:00Z",
                "notes": "Catch-up after network disruption"
            }
        ]
    }


def test_mode_context_contract_accepts_valid_payload(
    load_json_schema: Callable[[str | Path], dict]
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/mode_context.schema.json"
    )

    payload = _sample_mode_context_payload()

    validator.validate(payload)


def test_mode_context_contract_rejects_invalid_payload(
    load_json_schema: Callable[[str | Path], dict]
) -> None:
    validator = _build_validator(
        load_json_schema, "docs/schemas/mode_context.schema.json"
    )

    payload = _sample_mode_context_payload()
    broken = deepcopy(payload)
    broken["account_gateway"]["type"] = "invalid"

    with pytest.raises(ValidationError):
        validator.validate(broken)

    missing_mode = deepcopy(payload)
    del missing_mode["mode"]

    with pytest.raises(ValidationError):
        validator.validate(missing_mode)
