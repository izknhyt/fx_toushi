"""Fixed-response repository stub for scoreboard data."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(slots=True)
class ScoreRecord:
    strategy_id: str
    alpha_score: float
    decay_score: float
    status: str = "draft"


class ScoreboardRepositoryStub:
    def list_scores(self) -> Iterable[ScoreRecord]:
        return [
            ScoreRecord(
                strategy_id="m1_baseline_ma_rsi",
                alpha_score=78.5,
                decay_score=32.1,
                status="active",
            ),
            ScoreRecord(
                strategy_id="m1_baseline_donchian",
                alpha_score=71.0,
                decay_score=29.4,
                status="draft",
            ),
        ]


__all__ = ["ScoreRecord", "ScoreboardRepositoryStub"]
