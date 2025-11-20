"""Stability checker placeholder for perturbation tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StabilityEnvelope:
    baseline_score: float
    disturbed_score: float

    @property
    def drift(self) -> float:
        return round(self.disturbed_score - self.baseline_score, 6)

    def within_bounds(self, *, max_drift: float = 0.05) -> bool:
        return abs(self.drift) <= max_drift


__all__ = ["StabilityEnvelope"]
