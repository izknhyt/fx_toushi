"""Release audit logger for release gate events."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError


@dataclass(slots=True)
class ReleaseAuditLogger:
    """Persist release gate events to an audit log with schema validation."""

    path: Path = Path("logs/audit/release.jsonl")

    def record(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        entry = dict(payload)
        entry.setdefault("schema_version", "release.audit.v1")
        _validate_schema(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
        return entry


def _validate_schema(entry: Mapping[str, object]) -> None:
    validator = _load_validator()
    try:
        validator.validate(entry)
    except ValidationError as exc:
        raise ValueError(f"release audit schema validation failed: {exc.message}") from exc


@lru_cache(maxsize=1)
def _load_validator() -> Draft202012Validator:
    schema_path = Path("docs/schemas/release_audit.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


__all__ = ["ReleaseAuditLogger"]
