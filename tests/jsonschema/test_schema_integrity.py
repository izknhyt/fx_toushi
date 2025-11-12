"""Ensure every docs/schemas/*.schema.json is Draft 2020-12 compliant."""

from __future__ import annotations

from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

pytestmark = pytest.mark.json_schema_validation


@pytest.mark.parametrize(
    "schema_path",
    sorted(Path("docs/schemas").glob("*.schema.json")),
    ids=lambda path: path.stem,
)
def test_json_schemas_are_self_consistent(schema_path: Path, load_json_schema) -> None:
    """Every JSON Schema should pass Draft2020-12 validation."""

    schema = load_json_schema(schema_path)
    Draft202012Validator.check_schema(schema)
