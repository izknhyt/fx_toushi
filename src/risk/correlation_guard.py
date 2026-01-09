"""Correlation guard placeholder."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(slots=True)
class CorrelationSnapshot:
    pairs: Mapping[str, float]

    def breaches(self, threshold: float) -> list[str]:
        return [pair for pair, value in self.pairs.items() if abs(value) >= threshold]


class CorrelationGuard:
    def __init__(self, *, threshold: float = 0.85) -> None:
        self._threshold = threshold

    def evaluate(self, snapshot: CorrelationSnapshot) -> list[str]:
        return snapshot.breaches(self._threshold)


__all__ = ["CorrelationGuard", "CorrelationSnapshot"]
