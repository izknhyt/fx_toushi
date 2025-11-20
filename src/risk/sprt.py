"""Sequential Probability Ratio Test stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SprtResult:
    stop: bool
    reason: str | None = None


class SprtEvaluator:
    def __init__(self, *, alpha: float = 0.05, beta: float = 0.1) -> None:
        self.alpha = alpha
        self.beta = beta

    def evaluate(self, score: float) -> SprtResult:
        if score >= 1 - self.alpha:
            return SprtResult(stop=True, reason="accept")
        if score <= self.beta:
            return SprtResult(stop=True, reason="reject")
        return SprtResult(stop=False)


__all__ = ["SprtEvaluator", "SprtResult"]
