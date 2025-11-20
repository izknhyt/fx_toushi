"""Fixed fractional sizing helper."""

from __future__ import annotations


def fractional_size(equity: float, risk_pct: float, stop_distance: float) -> float:
    risk_amount = equity * (risk_pct / 100)
    if stop_distance <= 0:
        raise ValueError("stop_distance must be positive")
    return risk_amount / stop_distance


__all__ = ["fractional_size"]
