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
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        raise AssertionError(f"Config file {path} was empty")
    return data


CONFIG_CASES = [
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
]


@pytest.mark.parametrize(("name", "config_path", "schema_path"), CONFIG_CASES, ids=[name for name, *_ in CONFIG_CASES])
def test_config_files_match_schema(name: str, config_path: Path, schema_path: Path) -> None:
    """Validate each config YAML against its corresponding JSON Schema."""

    data = _load_yaml(config_path)
    validator = _build_validator(schema_path)
    validator.validate(data)
