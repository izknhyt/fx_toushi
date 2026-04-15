from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.cli.config import validate


def test_config_validate_success(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    target_path = tmp_path / "target.json"
    report_path = tmp_path / "report.md"

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["name"],
        "properties": {"name": {"type": "string"}},
    }
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    target_path.write_text(json.dumps({"name": "ok"}), encoding="utf-8")

    payload = validate(file=target_path, schema=schema_path, report_path=report_path)

    assert payload["status"] == "ok"
    assert report_path.exists()
