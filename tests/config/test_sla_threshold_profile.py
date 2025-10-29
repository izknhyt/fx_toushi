"""Validation tests for SLA threshold profile scaffolds."""

from collections.abc import Callable
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
Draft202012Validator = jsonschema.Draft202012Validator

pytestmark = pytest.mark.sla_threshold_config


def _build_validator(load_json_schema: Callable[[str | Path], dict]) -> Draft202012Validator:
    schema = load_json_schema("docs/schemas/sla_threshold_profile.schema.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.mark.parametrize("profile", ["default", "active"])
def test_sla_threshold_profile_matches_schema(
    profile: str,
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    """Ensure SLA threshold profiles adhere to their JSON Schema."""

    validator = _build_validator(load_json_schema)
    config = load_config(f"config/sla_thresholds/{profile}.yaml")

    validator.validate(config)


@pytest.mark.parametrize("profile", ["default", "active"])
def test_hitl_double_ack_minutes_present(
    profile: str,
    load_config: Callable[[str | Path], object],
) -> None:
    """The hitl section must include an explicit double_ack_minutes threshold."""

    config = load_config(f"config/sla_thresholds/{profile}.yaml")

    assert "hitl" in config, f"hitl thresholds missing in profile '{profile}'"

    hitl = config["hitl"]
    assert isinstance(hitl, dict), "hitl thresholds must be a mapping"
    assert "double_ack_minutes" in hitl, "double_ack_minutes threshold is required"

    value = hitl["double_ack_minutes"]
    assert isinstance(value, (int, float)), "double_ack_minutes must be numeric"
    assert value >= 0, "double_ack_minutes must be non-negative"
