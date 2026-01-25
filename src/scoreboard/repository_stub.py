"""Repository accessors for scoreboard data."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .service import DEFAULT_ALPHA_DIR


class ScoreboardRepositoryError(RuntimeError):
    """Raised when scoreboard data cannot be loaded."""


@dataclass(slots=True)
class ScoreRecord:
    strategy_id: str
    alpha_score: float
    decay_score: float
    status: str = "draft"


class ScoreboardRepository:
    def __init__(self, *, alpha_dir: Path = DEFAULT_ALPHA_DIR) -> None:
        self._alpha_dir = alpha_dir

    def list_scores(self) -> Iterable[ScoreRecord]:
        snapshot = self._load_latest()
        if snapshot is None:
            return []
        records: list[ScoreRecord] = []
        for entry in snapshot.get("strategies", []):
            strategy_id = entry.get("strategy_id")
            if not strategy_id:
                continue
            records.append(
                ScoreRecord(
                    strategy_id=strategy_id,
                    alpha_score=float(entry.get("alpha_score") or 0.0),
                    decay_score=float(entry.get("decay_score") or 0.0),
                    status=str(entry.get("status") or "unknown"),
                )
            )
        return records

    def _load_latest(self) -> dict[str, object] | None:
        if not self._alpha_dir.exists():
            return None
        candidates = sorted(
            self._alpha_dir.glob("*.json"),
            key=lambda path: (path.stat().st_mtime, path.name),
        )
        if not candidates:
            return None
        target = candidates[-1]
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ScoreboardRepositoryError(f"Scoreboard snapshot malformed: {target}") from exc


__all__ = ["ScoreRecord", "ScoreboardRepository", "ScoreboardRepositoryError"]
