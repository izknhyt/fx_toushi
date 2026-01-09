"""Grid search optimizer stub."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    parameters: Mapping[str, float]
    score: float


class GridSearchOptimizer:
    def optimise(self, grid: Mapping[str, Iterable[float]]) -> list[OptimizationResult]:
        keys = list(grid.keys())
        combos = product(*grid.values())
        results: list[OptimizationResult] = []
        for combo in combos:
            params = dict(zip(keys, combo, strict=False))
            score = sum(combo) / max(len(combo), 1)
            results.append(OptimizationResult(parameters=params, score=score))
        results.sort(key=lambda item: item.score, reverse=True)
        return results


__all__ = ["GridSearchOptimizer", "OptimizationResult"]
