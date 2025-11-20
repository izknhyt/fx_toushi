"""Strategy ranking helpers for §1.3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True, slots=True)
class RankingInput:
    strategy_id: str
    pf_all: float
    sharpe_all: float
    max_drawdown: float
    latency_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class RankingResult:
    strategy_id: str
    score: float
    rank: int
    details: dict[str, float]


def _score(entry: RankingInput) -> float:
    pf_component = entry.pf_all
    sharpe_component = entry.sharpe_all
    drawdown_penalty = max(0.0, entry.max_drawdown - 0.1) * 5
    latency_penalty = min(entry.latency_ms / 1000, 1.0)
    return pf_component + sharpe_component - drawdown_penalty - latency_penalty


def rank_strategies(entries: Iterable[RankingInput]) -> List[RankingResult]:
    scored = [(entry, _score(entry)) for entry in entries]
    scored.sort(key=lambda item: item[1], reverse=True)
    results: list[RankingResult] = []
    for index, (entry, score) in enumerate(scored, start=1):
        results.append(
            RankingResult(
                strategy_id=entry.strategy_id,
                score=round(score, 4),
                rank=index,
                details={
                    "pf": entry.pf_all,
                    "sharpe": entry.sharpe_all,
                    "max_drawdown": entry.max_drawdown,
                    "latency_ms": entry.latency_ms,
                },
            )
        )
    return results


__all__ = ["RankingInput", "RankingResult", "rank_strategies"]
