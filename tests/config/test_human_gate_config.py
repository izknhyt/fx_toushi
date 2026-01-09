"""Validation tests for Human Gate / Reduce-Only configuration scaffolds."""

from collections.abc import Callable
from pathlib import Path

import pytest

from jsonschema import Draft202012Validator

pytestmark = pytest.mark.reduce_only_config


def _build_validator(load_json_schema: Callable[[str | Path], dict]) -> Draft202012Validator:
    schema = load_json_schema("docs/schemas/human_gate_config.schema.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_reduce_only_config_matches_schema(
    load_json_schema: Callable[[str | Path], dict],
    load_config: Callable[[str | Path], object],
) -> None:
    """Ensure the reduce-only config scaffold adheres to its JSON Schema."""

    validator = _build_validator(load_json_schema)
    config = load_config("config/reduce_only.yaml")

    validator.validate(config)


@pytest.mark.parametrize("profile", ["backtest", "paper", "live"])
def test_profile_gate_overrides_are_consistent(
    profile: str,
    load_config: Callable[[str | Path], object],
) -> None:
    """Profiles must respect the base Human Gate contract when overriding fields."""

    base_config = load_config("config/reduce_only.yaml")
    human_gate = base_config["human_gate"]
    base_required_roles = set(human_gate["required_roles"])
    double_ack_roles = set(human_gate["double_ack_roles"])
    base_comment_min = int(human_gate["comment_min_length"])
    base_comment_max = int(human_gate["comment_max_length"])

    gates = load_config(f"config/profiles/{profile}.yaml")["gates"]

    required_roles = set(gates.get("required_roles", human_gate["required_roles"]))
    assert required_roles.issuperset(base_required_roles)
    assert required_roles.issuperset(double_ack_roles)

    comment_min = int(gates.get("comment_min_length", base_comment_min))
    comment_max = int(gates.get("comment_max_length", base_comment_max))
    assert comment_min >= 0
    assert comment_min <= comment_max <= base_comment_max

    if "manual_comment_required" in gates:
        assert isinstance(gates["manual_comment_required"], bool)
