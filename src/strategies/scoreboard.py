"""Strategy scoreboard helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(slots=True)
class StrategyScoreSnapshot:
    strategy_id: str
    alpha_score: float
    decay_score: float | None
    ts: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "alpha_score": self.alpha_score,
            "decay_score": self.decay_score,
            "ts": self.ts,
        }


class StrategyScoreboardService:
    def __init__(self, *, metrics_path: Path = Path("metrics/strategy_scores.jsonl")) -> None:
        self._metrics_path = metrics_path

    def load_scores(self) -> list[StrategyScoreSnapshot]:
        if not self._metrics_path.exists():
            return []
        entries: list[StrategyScoreSnapshot] = []
        for line in self._metrics_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            strategy_id = payload.get("strategy_id") or payload.get("id")
            if not strategy_id:
                continue
            entries.append(
                StrategyScoreSnapshot(
                    strategy_id=str(strategy_id),
                    alpha_score=float(payload.get("alpha_score") or 0.0),
                    decay_score=_optional_float(payload.get("decay_score")),
                    ts=payload.get("ts"),
                )
            )
        return entries

    def watchlist(self, *, threshold: float = 70.0) -> list[Mapping[str, object]]:
        watchlist: list[Mapping[str, object]] = []
        for entry in self.load_scores():
            if entry.alpha_score < threshold:
                watchlist.append(
                    {
                        "strategy_id": entry.strategy_id,
                        "alpha_score": entry.alpha_score,
                        "decay_score": entry.decay_score,
                    }
                )
        return watchlist


def _optional_float(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["StrategyScoreboardService", "StrategyScoreSnapshot"]
