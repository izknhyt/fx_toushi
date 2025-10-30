from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

pytestmark = pytest.mark.smoke


def _build_validator(
    load_json_schema: Callable[[str | Path], dict],
    schema_path: str,
) -> Draft202012Validator:
    schema = load_json_schema(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


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
