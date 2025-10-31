"""Risk Manager scaffold responsible for basic kill switch guidance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.core.gate import RiskGateState

__all__ = ["RiskAssessment", "RiskManager", "RiskSnapshot"]


@dataclass(slots=True)
class RiskSnapshot:
    """Minimal set of metrics required to issue risk guidance."""

    daily_drawdown_pct: float = 0.0
    weekly_drawdown_pct: float = 0.0
    equity_pct_of_base: float | None = None
    exposure_r_eff: float | None = None


@dataclass(slots=True)
class RiskAssessment:
    """Outcome of a risk evaluation cycle."""

    risk_state: RiskGateState
    kill_switch_suggestion: str | None
    kill_switch_reason: str | None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_state": self.risk_state.to_dict(),
            "kill_switch_suggestion": self.kill_switch_suggestion,
            "kill_switch_reason": self.kill_switch_reason,
        }


class RiskManager:
    """Evaluate drawdown and exposure signals for Kill Switch guidance."""

    def __init__(
        self,
        *,
        daily_stop_pct: float = 2.5,
        weekly_stop_pct: float = 5.0,
        r_eff_soft_stop: float = 2.0,
        r_eff_hard_stop: float = 2.5,
        capital_floor_pct: float = 80.0,
    ) -> None:
        self._daily_stop_pct = daily_stop_pct
        self._weekly_stop_pct = weekly_stop_pct
        self._r_eff_soft_stop = r_eff_soft_stop
        self._r_eff_hard_stop = r_eff_hard_stop
        self._capital_floor_pct = capital_floor_pct

    def evaluate(self, snapshot: RiskSnapshot) -> RiskAssessment:
        """Evaluate the latest metrics and recommend guard rails."""

        reduce_only = False
        reduce_only_reason: str | None = None
        kill_switch: str | None = None
        kill_switch_reason: str | None = None

        if snapshot.exposure_r_eff is not None:
            if snapshot.exposure_r_eff >= self._r_eff_hard_stop:
                kill_switch = "hard_stop"
                kill_switch_reason = "r_eff_hard_stop"
            elif snapshot.exposure_r_eff >= self._r_eff_soft_stop:
                reduce_only = True
                reduce_only_reason = "r_eff_soft_stop"

        if snapshot.daily_drawdown_pct >= self._daily_stop_pct:
            kill_switch = "soft_stop"
            kill_switch_reason = "daily_drawdown"

        if snapshot.weekly_drawdown_pct >= self._weekly_stop_pct:
            kill_switch = "soft_stop"
            kill_switch_reason = "weekly_drawdown"

        if (
            snapshot.equity_pct_of_base is not None
            and snapshot.equity_pct_of_base <= self._capital_floor_pct
        ):
            kill_switch = "hard_stop"
            kill_switch_reason = "capital_floor"

        risk_state = RiskGateState(
            reduce_only=reduce_only,
            reduce_only_reason=reduce_only_reason,
            kill_switch_recommendation=kill_switch,
            kill_switch_reason=kill_switch_reason,
        )

        return RiskAssessment(
            risk_state=risk_state,
            kill_switch_suggestion=kill_switch,
            kill_switch_reason=kill_switch_reason,
        )
