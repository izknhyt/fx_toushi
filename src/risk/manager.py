"""Risk Manager scaffold responsible for basic kill switch guidance."""

from __future__ import annotations

from collections.abc import Callable
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.funding import FundingCurve
from src.core.health import HealthMonitor

from src.core.gate import GateState, RiskGateState

__all__ = ["RiskAssessment", "RiskDecision", "RiskManager", "RiskSnapshot"]

DEFAULT_RISK_POLICY_PATH = Path("config") / "risk_policy.yaml"
DEFAULT_RISK_DECISION_LOG = Path("logs") / "events" / "risk.decision.jsonl"


@dataclass(slots=True)
class RiskSnapshot:
    """Minimal set of metrics required to issue risk guidance."""

    daily_drawdown_pct: float = 0.0
    weekly_drawdown_pct: float = 0.0
    equity_pct_of_base: float | None = None
    exposure_r_eff: float | None = None
    spread_status: str | None = None
    session_date: date | None = None
    funding_rate: float | None = None


@dataclass(slots=True)
class RiskAssessment:
    """Outcome of a risk evaluation cycle."""

    risk_state: RiskGateState
    kill_switch_suggestion: str | None
    kill_switch_reason: str | None
    funding_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_state": self.risk_state.to_dict(),
            "kill_switch_suggestion": self.kill_switch_suggestion,
            "kill_switch_reason": self.kill_switch_reason,
            "funding_rate": self.funding_rate,
        }


ReduceOnlyAdvisor = Callable[
    [GateState, RiskAssessment | None, str, str], tuple[bool, str | None]
]


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
        reduce_only_advisor: ReduceOnlyAdvisor | None = None,
        funding_curve: FundingCurve | None = None,
        risk_decision_log_path: Path | None = None,
    ) -> None:
        self._daily_stop_pct = daily_stop_pct
        self._weekly_stop_pct = weekly_stop_pct
        self._r_eff_soft_stop = r_eff_soft_stop
        self._r_eff_hard_stop = r_eff_hard_stop
        self._capital_floor_pct = capital_floor_pct
        self._reduce_only_advisor = reduce_only_advisor
        self._funding_curve = funding_curve
        self._risk_decision_log_path = risk_decision_log_path or DEFAULT_RISK_DECISION_LOG

    @classmethod
    def from_policy(
        cls,
        *,
        path: Path = DEFAULT_RISK_POLICY_PATH,
        profile: str = "m1_baseline",
        funding_curve: FundingCurve | None = None,
        risk_decision_log_path: Path | None = None,
    ) -> RiskManager:
        """Build a RiskManager using thresholds from risk_policy.yaml."""

        daily_stop = 2.5
        weekly_stop = 5.0
        r_eff_soft = 2.0
        r_eff_hard = 2.5
        capital_floor = 80.0
        if path.exists():
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            profiles = payload.get("profiles", {})
            profile_cfg = profiles.get(profile, {}) if isinstance(profiles, dict) else {}
            risk_limits = profile_cfg.get("risk_limits", {}) if isinstance(profile_cfg, dict) else {}
            kill_switch = profile_cfg.get("kill_switch", {}) if isinstance(profile_cfg, dict) else {}
            drawdown = kill_switch.get("drawdown_threshold_pct", {})
            if isinstance(drawdown, dict):
                daily_stop = float(drawdown.get("daily", daily_stop))
                weekly_stop = float(drawdown.get("weekly", weekly_stop))
            capital_floor = float(
                kill_switch.get("capital_floor_pct_of_base", capital_floor)
            )
            r_eff_soft = float(
                risk_limits.get("exposure_r_eff_soft_stop", r_eff_soft)
            )
            r_eff_hard = float(
                risk_limits.get("exposure_r_eff_hard_stop", r_eff_hard)
            )
        return cls(
            daily_stop_pct=daily_stop,
            weekly_stop_pct=weekly_stop,
            r_eff_soft_stop=r_eff_soft,
            r_eff_hard_stop=r_eff_hard,
            capital_floor_pct=capital_floor,
            funding_curve=funding_curve,
            risk_decision_log_path=risk_decision_log_path,
        )

    def evaluate(
        self,
        snapshot: RiskSnapshot,
        *,
        health_monitor: HealthMonitor | None = None,
    ) -> RiskAssessment:
        """Evaluate the latest metrics and recommend guard rails."""

        reduce_only = False
        reduce_only_reason: str | None = None
        kill_switch: str | None = None
        kill_switch_reason: str | None = None
        funding_rate = snapshot.funding_rate
        if funding_rate is None and self._funding_curve and snapshot.session_date:
            funding_rate = self._funding_curve.rate_on(snapshot.session_date)

        if snapshot.exposure_r_eff is not None:
            if snapshot.exposure_r_eff >= self._r_eff_hard_stop:
                kill_switch = "hard_stop"
                kill_switch_reason = "r_eff_hard_stop"
            elif snapshot.exposure_r_eff >= self._r_eff_soft_stop:
                reduce_only = True
                reduce_only_reason = "r_eff_soft_stop"

        spread_status = (snapshot.spread_status or "").lower()
        if spread_status in {"block", "halt"}:
            kill_switch = "soft_stop"
            kill_switch_reason = "spread_block"
        elif spread_status in {"cooldown", "watch"} and not reduce_only:
            reduce_only = True
            reduce_only_reason = "spread_cooldown"

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

        monitor = health_monitor or HealthMonitor()
        if kill_switch:
            level = "critical" if kill_switch == "hard_stop" else "warning"
            monitor.raise_condition(
                level,
                "risk_kill_switch",
                detail=kill_switch_reason,
                recommended_action="runbook:RUN-RISK-01#kill-switch",
            )
        elif reduce_only:
            monitor.raise_condition(
                "warning",
                "risk_reduce_only",
                detail=reduce_only_reason,
                recommended_action="runbook:RUN-RISK-01#reduce-only",
            )

        return RiskAssessment(
            risk_state=risk_state,
            kill_switch_suggestion=kill_switch,
            kill_switch_reason=kill_switch_reason,
            funding_rate=funding_rate,
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
        reduce_only_reason = gate.risk.reduce_only_reason
        if assessment and assessment.risk_state.reduce_only_reason:
            reduce_only_reason = assessment.risk_state.reduce_only_reason
        advisor_reduce_only, advisor_reason = self._evaluate_reduce_only_advisor(
            gate_state=gate,
            assessment=assessment,
            spread_status=effective_spread,
            kill_switch_state=kill_switch_effective,
        )
        if advisor_reduce_only:
            reduce_only = True
            if reduce_only_reason is None:
                reduce_only_reason = advisor_reason or "reduce_only_advisor"

        reason = (
            gate.market.spread.reason
            or gate.risk.kill_switch_reason
            or (assessment.kill_switch_reason if assessment else None)
            or reduce_only_reason
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

        decision = RiskDecision(
            allowed=allowed,
            reduce_only=reduce_only,
            board_mode=board_mode,
            kill_switch_state=kill_switch_effective,
            spread_status=effective_spread,
            reason=reason,
            exit_code=exit_code,
        )
        self._emit_risk_decision(
            decision=decision,
            actor=actor,
            runbook=runbook,
            gate_state=gate,
        )
        return decision

    def _evaluate_reduce_only_advisor(
        self,
        *,
        gate_state: GateState,
        assessment: RiskAssessment | None,
        spread_status: str,
        kill_switch_state: str,
    ) -> tuple[bool, str | None]:
        if self._reduce_only_advisor is None:
            return False, None
        result = self._reduce_only_advisor(
            gate_state, assessment, spread_status, kill_switch_state
        )
        if isinstance(result, tuple) and len(result) == 2:
            return bool(result[0]), result[1]
        return bool(result), None

    def _emit_risk_decision(
        self,
        *,
        decision: RiskDecision,
        actor: str | None,
        runbook: str | None,
        gate_state: GateState,
    ) -> None:
        payload = {
            "event": "risk.decision",
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "actor": actor,
            "runbook_ref": runbook,
            "decision": decision.to_dict(),
            "gate": gate_state.to_dict(),
        }
        try:
            _append_jsonl(self._risk_decision_log_path, payload)
        except OSError:
            return


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")
