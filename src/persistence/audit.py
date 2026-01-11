"""Audit log writer implementing ticket.action v2 schema."""

from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache

from jsonschema import Draft202012Validator, ValidationError


@dataclass(slots=True)
class AuditWriter:
    """Persist ticket.action audit records to both raw and validated logs."""

    path: Path = Path("audit/ticket_actions.jsonl")
    compliance_path: Path = Path("logs/audit/hitl.jsonl")

    def record_ticket_action(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        entry: MutableMapping[str, object] = dict(payload)
        entry.setdefault("spread_state", {})
        if "health_status" not in entry:
            guardrails = entry.get("guardrails")
            if isinstance(guardrails, Mapping):
                health_status = guardrails.get("health_state") or guardrails.get("health_status")
                if health_status is not None:
                    entry["health_status"] = health_status
        AuditLogger(path=self.compliance_path).record(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
        return entry


class AuditLogger:
    def __init__(self, path: str | Path = "logs/audit/hitl.jsonl") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        """Append an audit record ensuring ticket.action.v2 required fields."""

        entry: MutableMapping[str, object] = dict(payload)
        _validate_required_fields(entry)
        _validate_schema(entry)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
        return entry


def _validate_required_fields(entry: Mapping[str, object]) -> None:
    required = {
        "ts",
        "schema_version",
        "ticket_id",
        "action",
        "actor",
        "board_mode",
        "kill_switch_state",
        "spread_status",
        "profit_readiness_status",
        "reduce_only",
        "risk_disclosure_state",
        "cfg_hash",
        "data_hash",
        "consent_reference_id",
        "record_type",
        "delta",
        "guardrails",
    }
    missing = [key for key in sorted(required) if key not in entry]
    if missing:
        raise ValueError(f"audit record missing required fields: {', '.join(missing)}")
    delta = entry.get("delta")
    if not isinstance(delta, Mapping):
        raise ValueError("audit record delta must be an object")
    for key in ("before", "after", "diff", "decision"):
        if key not in delta:
            raise ValueError(f"audit record delta missing required field: {key}")
    guardrails = entry.get("guardrails")
    if not isinstance(guardrails, Mapping):
        raise ValueError("audit record guardrails must be an object")
    for key in ("kill_switch", "spread_status", "reduce_only"):
        if key not in guardrails:
            raise ValueError(f"audit record guardrails missing required field: {key}")


def _validate_schema(entry: Mapping[str, object]) -> None:
    validator = _load_validator()
    try:
        validator.validate(entry)
    except ValidationError as exc:
        raise ValueError(f"audit record schema validation failed: {exc.message}") from exc


@lru_cache(maxsize=1)
def _load_validator() -> Draft202012Validator:
    schema_path = Path("docs/schemas/audit_ticket_action.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


__all__ = ["AuditLogger", "AuditWriter"]
