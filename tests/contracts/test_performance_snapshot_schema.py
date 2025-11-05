from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

pytestmark = pytest.mark.contracts


def _load_sample(project_root: Path) -> dict:
    """Load the canonical performance snapshot example."""

    sample_path = (
        project_root / "docs/schemas/examples/performance_snapshot.sample.json"
    )
    return json.loads(sample_path.read_text(encoding="utf-8"))


def test_performance_snapshot_sample_is_contract_compliant(
    load_json_schema, project_root: Path
) -> None:
    """Ensure the curated sample document conforms to the schema contract."""

    schema = load_json_schema("docs/schemas/performance_snapshot.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    sample = _load_sample(project_root)

    validator.validate(sample)


def test_performance_snapshot_rejects_invalid_payload(
    load_json_schema, project_root: Path
) -> None:
    """Reject snapshots that fail fundamental constraints (UTC timestamps, KPI bounds)."""

    schema = load_json_schema("docs/schemas/performance_snapshot.schema.json")
    validator = Draft202012Validator(schema)

    invalid_snapshot = deepcopy(_load_sample(project_root))
    invalid_snapshot["timestamp"] = "2025-03-18T09:30:00"  # missing Z suffix
    invalid_snapshot["metrics"]["win_rate"] = 1.2  # exceeds permissible range

    with pytest.raises(ValidationError):
        validator.validate(invalid_snapshot)

