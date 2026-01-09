"""Snapshot persistence stub."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path


class SnapshotStore:
    def __init__(self, path: str | Path = "snapshots/state.json") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, payload: Mapping[str, object]) -> None:
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> Mapping[str, object] | None:
        if not self._path.exists():
            return None
        return json.loads(self._path.read_text(encoding="utf-8"))


__all__ = ["SnapshotStore"]
