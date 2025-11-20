"""Hybrid scoring placeholder (M2+)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HybridScore:
    alpha_score: float
    decay_score: float
    stability_score: float
    enabled: bool = False

    @property
    def composite(self) -> float:
        if not self.enabled:
            return 0.0
        return round((self.alpha_score * 0.5) + (self.decay_score * 0.3) + (self.stability_score * 0.2), 4)


def compute_hybrid_score(alpha: float, decay: float, stability: float, *, enabled: bool = False) -> HybridScore:
    return HybridScore(alpha_score=alpha, decay_score=decay, stability_score=stability, enabled=enabled)


__all__ = ["HybridScore", "compute_hybrid_score"]
