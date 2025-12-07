"""Audit log writer implementing ticket.action v2 schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, MutableMapping


class AuditLogger:
    def __init__(self, path: str | Path = "logs/audit/hitl.jsonl") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        """Append an audit record ensuring ticket.action.v2 required fields."""

        entry: MutableMapping[str, object] = dict(payload)
        entry.setdefault("schema_version", "ticket.action.v2")
        delta = entry.get("delta")
        if not isinstance(delta, Mapping):
            delta = {"before": {}, "after": {}, "diff": {}}
        else:
            delta = dict(delta)
            delta.setdefault("before", {})
            delta.setdefault("after", {})
            delta.setdefault("diff", {})
        entry["delta"] = delta
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
        return entry


__all__ = ["AuditLogger"]
