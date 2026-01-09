"""No-op scoreboard service stub for M1."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ScoreboardSnapshot:
    week: str
    strategies: tuple[Mapping[str, object], ...]


class StrategyScoreboardServiceStub:
    """Publishes placeholders so CLI/tests can proceed without the full service."""

    def publish(self, snapshot: ScoreboardSnapshot) -> None:
        logger.info(
            "scoreboard.stub.publish",
            extra={"week": snapshot.week, "count": len(snapshot.strategies)},
        )

    def build_snapshot(self, strategies: Iterable[Mapping[str, object]]) -> ScoreboardSnapshot:
        week = datetime.now(timezone.utc).strftime("%Y-W%V")
        return ScoreboardSnapshot(week=week, strategies=tuple(strategies))


__all__ = ["ScoreboardSnapshot", "StrategyScoreboardServiceStub"]
