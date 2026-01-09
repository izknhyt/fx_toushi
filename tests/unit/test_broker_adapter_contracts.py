from __future__ import annotations

import json
from dataclasses import is_dataclass
from pathlib import Path

import pytest
from src.brokers.adapter import (
    CTRADER_ENDPOINTS,
    MT5_ENDPOINTS,
    ORDER_FIELD_MAPPING,
    RATE_LIMIT_SLA,
    EndpointSpec,
    FieldMapping,
)

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "broker_adapter.json"


def load_contract_fixture() -> dict:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover - fails fast in CI without fixture
        raise RuntimeError("broker adapter fixture missing") from exc


def test_metadata_dataclasses_are_frozen() -> None:
    for cls in (EndpointSpec, FieldMapping):
        assert is_dataclass(cls), f"{cls.__name__} must remain a dataclass"
        assert cls.__dataclass_params__.frozen, f"{cls.__name__} must be frozen=True"


@pytest.mark.parametrize("endpoint_table", [MT5_ENDPOINTS, CTRADER_ENDPOINTS])
def test_endpoint_specs_use_frozen_dataclass_instances(endpoint_table) -> None:
    # Dataclass instances should be immutable to avoid accidental drift from design docs.
    for spec in endpoint_table:
        assert isinstance(spec, EndpointSpec)


def test_field_mapping_contract() -> None:
    fixture = load_contract_fixture()
    required_fields = set(fixture["required_ticket_fields"])
    allowed_directions = set(fixture["allowed_directions"])

    observed_fields = {mapping.ticket_field for mapping in ORDER_FIELD_MAPPING}
    assert (
        observed_fields == required_fields
    ), f"Field mappings differ from fixture: {observed_fields ^ required_fields}"

    for mapping in ORDER_FIELD_MAPPING:
        assert (
            mapping.direction in allowed_directions
        ), f"Unexpected direction '{mapping.direction}' for {mapping.ticket_field}"


def test_rate_limit_sla_strings_match_design() -> None:
    fixture = load_contract_fixture()["rate_limit_sla"]

    for adapter, expectations in fixture.items():
        assert adapter in RATE_LIMIT_SLA, f"Missing adapter '{adapter}' in RATE_LIMIT_SLA"

        actual_index = {entry["endpoint"]: entry for entry in RATE_LIMIT_SLA[adapter]}
        for endpoint, expected_values in expectations.items():
            assert (
                endpoint in actual_index
            ), f"Missing endpoint '{endpoint}' for adapter '{adapter}'"
            for key in ("limit", "sla", "retry_policy"):
                actual_value = actual_index[endpoint][key]
                expected_value = expected_values[key]
                assert (
                    actual_value == expected_value
                ), f"{adapter}.{endpoint}.{key} mismatch: {actual_value!r} != {expected_value!r}"
