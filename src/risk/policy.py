"""Risk policy dataclass for §1.3."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RiskPolicy:
    daily_stop_pct: float = 2.5
    weekly_stop_pct: float = 5.0
    capital_floor_pct: float = 80.0
    r_eff_soft_stop: float = 2.0
    r_eff_hard_stop: float = 2.5


__all__ = ["RiskPolicy"]
