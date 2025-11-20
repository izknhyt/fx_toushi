"""Audit log writer stub."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping


class AuditLogger:
    def __init__(self, path: str | Path = "logs/audit/hitl.jsonl") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, payload: Mapping[str, object]) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("
")


__all__ = ["AuditLogger"]
