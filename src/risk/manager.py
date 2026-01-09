"""Risk Manager scaffold responsible for basic kill switch guidance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.gate import GateState, RiskGateState

__all__ = ["RiskAssessment", "RiskDecision", "RiskManager", "RiskSnapshot"]


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_state": self.risk_state.to_dict(),
            "kill_switch_suggestion": self.kill_switch_suggestion,
            "kill_switch_reason": self.kill_switch_reason,
        }


@dataclass(slots=True)
class RiskDecision:
    """Decision payload for ticket/board evaluation."""

    allowed: bool
    reduce_only: bool
    board_mode: str
    kill_switch_state: str
    spread_status: str
    reason: str | None
    exit_code: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reduce_only": self.reduce_only,
            "board_mode": self.board_mode,
            "kill_switch_state": self.kill_switch_state,
            "spread_status": self.spread_status,
            "reason": self.reason,
            "exit_code": self.exit_code,
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

    @staticmethod
    def _normalise_spread_state(spread_state: str | None) -> str:
        if spread_state in {"halt", "block"}:
            return "block"
        if spread_state in {"cooldown", "watch"}:
            return "cooldown"
        return "normal"

    def evaluate_ticket(
        self,
        *,
        gate_state: GateState | None = None,
        assessment: RiskAssessment | None = None,
        spread_status: str | None = None,
        kill_switch_state: str | None = None,
        actor: str | None = None,
        runbook: str | None = None,
    ) -> RiskDecision:
        """Evaluate guardrails for ticket/board operations."""

        gate = gate_state or GateState()
        effective_spread = self._normalise_spread_state(spread_status or gate.market.spread.state)
        kill_switch_effective = (
            kill_switch_state
            or (assessment.kill_switch_suggestion if assessment else None)
            or gate.risk.kill_switch_recommendation
            or "none"
        )

        reduce_only = gate.risk.reduce_only or (
            assessment.risk_state.reduce_only if assessment else False
        )
        reason = (
            gate.market.spread.reason
            or gate.risk.kill_switch_reason
            or (assessment.kill_switch_reason if assessment else None)
        )

        board_mode = "normal"
        allowed = True
        exit_code = 0

        if kill_switch_effective == "hard_stop":
            board_mode = "halted"
            allowed = False
            exit_code = 63
            reason = reason or "kill_switch_hard_stop"
        elif effective_spread == "block":
            board_mode = "guarded"
            allowed = False
            reduce_only = True
            exit_code = 62
            reason = reason or "spread_block"
            kill_switch_effective = kill_switch_effective or "soft_stop"
        elif kill_switch_effective == "soft_stop":
            board_mode = "guarded"
            allowed = False
            reduce_only = True
            exit_code = 62
            reason = reason or "kill_switch_soft_stop"
        elif effective_spread == "cooldown" or reduce_only:
            board_mode = "guarded"
            exit_code = 21
            reason = reason or ("reduce_only" if reduce_only else "spread_cooldown")

        return RiskDecision(
            allowed=allowed,
            reduce_only=reduce_only,
            board_mode=board_mode,
            kill_switch_state=kill_switch_effective,
            spread_status=effective_spread,
            reason=reason,
            exit_code=exit_code,
        )
