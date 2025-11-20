"""Ops readiness evaluator stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OpsReadinessResult:
    score: float
    notes: str


class OpsReadinessEvaluatorStub:
    def evaluate(self) -> OpsReadinessResult:
        return OpsReadinessResult(score=0.0, notes="Not Assessed")


__all__ = ["OpsReadinessEvaluatorStub", "OpsReadinessResult"]
