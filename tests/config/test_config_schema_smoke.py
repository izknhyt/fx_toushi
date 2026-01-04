"""Smoke-tests ensuring config scaffolds match their JSON Schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from src.core.schema_registry import build_schema_registry

pytestmark = pytest.mark.config_schema_smoke


def _build_validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    registry = build_schema_registry(schema_path)
    return Draft202012Validator(schema, registry=registry)


def _load_yaml(path: Path) -> Any:
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        raise AssertionError(f"Config file {path} was empty")
    return data


CONFIG_CASES = [
    ("alpha_profiles", Path("config/alpha_profiles.yaml"), Path("docs/schemas/alpha_profiles.schema.json")),
    ("board_modes", Path("config/board_modes.yaml"), Path("docs/schemas/board_modes.schema.json")),
    ("feature_flags", Path("config/feature_flags.yaml"), Path("docs/schemas/feature_flags.schema.json")),
    ("feature_pipeline", Path("config/feature_pipeline.yaml"), Path("docs/schemas/feature_pipeline.schema.json")),
    ("execution_model", Path("config/execution_model.yaml"), Path("docs/schemas/execution_model.schema.json")),
    ("risk_policy", Path("config/risk_policy.yaml"), Path("docs/schemas/risk_policy.schema.json")),
    ("risk_live_guard", Path("config/risk_live_guard.yaml"), Path("docs/schemas/risk_live_guard.schema.json")),
    ("ops_config", Path("config/ops.yaml"), Path("docs/schemas/ops_config.schema.json")),
    ("ops_readiness", Path("config/ops_readiness.yaml"), Path("docs/schemas/ops_readiness.schema.json")),
    ("roles", Path("config/roles.yaml"), Path("docs/schemas/roles_config.schema.json")),
    ("scoring", Path("config/scoring.yaml"), Path("docs/schemas/scoring_config.schema.json")),
    ("scoreboard", Path("config/scoreboard.yaml"), Path("docs/schemas/scoreboard.schema.json")),
    ("sla_threshold_default", Path("config/sla_thresholds/default.yaml"), Path("docs/schemas/sla_threshold_profile.schema.json")),
    ("sla_threshold_active", Path("config/sla_thresholds/active.yaml"), Path("docs/schemas/sla_threshold_profile.schema.json")),
    ("profile_backtest", Path("config/profiles/backtest.yaml"), Path("docs/schemas/cfg.schema.json")),
    ("profile_paper", Path("config/profiles/paper.yaml"), Path("docs/schemas/cfg.schema.json")),
    ("profile_live", Path("config/profiles/live.yaml"), Path("docs/schemas/cfg.schema.json")),
    ("broker_sandbox", Path("config/brokers/sandbox.yaml"), Path("docs/schemas/broker_sandbox.schema.json")),
    ("broker_error_map", Path("config/brokers/error_map.yaml"), Path("docs/schemas/broker_error_map.schema.json")),
    ("broker_slo", Path("config/brokers/slo.yaml"), Path("docs/schemas/broker_slo.schema.json")),
    ("business_days", Path("config/calendar/business_days.yaml"), Path("docs/schemas/business_days.schema.json")),
    ("pretrade_rules_template", Path("config/compliance/pretrade_rules_TEMPLATE.yaml"), Path("docs/schemas/compliance_pretrade_rules.schema.json")),
    ("risk_disclosure_template", Path("config/compliance/risk_disclosure_TEMPLATE.yaml"), Path("docs/schemas/compliance_risk_disclosure.schema.json")),
    ("concurrency_profiles", Path("config/concurrency_profiles.yaml"), Path("docs/schemas/concurrency_profiles.schema.json")),
    ("drift_monitor", Path("config/drift_monitor.yaml"), Path("docs/schemas/drift_monitor.schema.json")),
    ("emergency", Path("config/emergency.yaml"), Path("docs/schemas/emergency.schema.json")),
    ("hedge_routes", Path("config/hedge_routes.yaml"), Path("docs/schemas/hedge_routes.schema.json")),
    ("idea_pipeline", Path("config/idea_pipeline.yaml"), Path("docs/schemas/idea_pipeline.schema.json")),
    ("ideas", Path("config/ideas.yaml"), Path("docs/schemas/ideas.schema.json")),
    ("model_risk", Path("config/model_risk.yaml"), Path("docs/schemas/model_risk.schema.json")),
    ("ops_workload_defaults", Path("config/ops/workload_defaults.yaml"), Path("docs/schemas/ops_workload_defaults.schema.json")),
    ("real_time_candidates", Path("config/providers/real_time_candidates.yaml"), Path("docs/schemas/real_time_candidates.schema.json")),
    ("reconciliation", Path("config/reconciliation.yaml"), Path("docs/schemas/reconciliation.schema.json")),
    ("regression", Path("config/regression.yaml"), Path("docs/schemas/regression.schema.json")),
    ("reports_kpi", Path("config/reports/kpi.yaml"), Path("docs/schemas/reports_kpi.schema.json")),
    ("resource_budget", Path("config/resource_budget.yaml"), Path("docs/schemas/resource_budget.schema.json")),
    ("margin_stress_presets", Path("config/risk/margin_stress_presets.yaml"), Path("docs/schemas/margin_stress_presets.schema.json")),
    ("shadow_channels", Path("config/shadow/channels.yaml"), Path("docs/schemas/shadow_channels.schema.json")),
    ("shadow_tokens", Path("config/shadow/tokens.yaml"), Path("docs/schemas/shadow_tokens.schema.json")),
    ("share_profiles_template", Path("config/share_profiles/TEMPLATE.yaml"), Path("docs/schemas/share_profiles.schema.json")),
    ("signatures_index", Path("config/signatures/index.json"), Path("docs/schemas/signatures_index.schema.json")),
    ("sla_threshold_candidate", Path("config/sla_thresholds/candidate_template.yaml"), Path("docs/schemas/sla_threshold_candidate.schema.json")),
    ("provider_priority", Path("config/provider_priority.yaml"), Path("docs/schemas/provider_priority.schema.json")),
    ("ingestion_priorities", Path("config/ingestion/priorities.yaml"), Path("docs/schemas/ingestion_priorities.schema.json")),
    ("event_bus", Path("config/event_bus.yaml"), Path("docs/schemas/event_bus.schema.json")),
    ("pipeline_steps", Path("config/pipeline/m1_core.yaml"), Path("docs/schemas/pipeline_steps.schema.json")),
    ("data_source_dukascopy", Path("config/data_sources/dukascopy.yaml"), Path("docs/schemas/data_source.schema.json")),
    ("data_source_yfinance", Path("config/data_sources/yfinance.yaml"), Path("docs/schemas/data_source.schema.json")),
    ("data_source_template", Path("config/data_sources/TEMPLATE.yaml"), Path("docs/schemas/data_source.schema.json")),
]


@pytest.mark.parametrize(("name", "config_path", "schema_path"), CONFIG_CASES, ids=[name for name, *_ in CONFIG_CASES])
def test_config_files_match_schema(name: str, config_path: Path, schema_path: Path) -> None:
    """Validate each config YAML against its corresponding JSON Schema."""

    data = _load_yaml(config_path)
    validator = _build_validator(schema_path)
    validator.validate(data)
