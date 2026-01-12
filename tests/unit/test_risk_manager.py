"""Risk manager guardrail evaluation tests."""

from __future__ import annotations

from src.core.gate import GateState
from datetime import date

from src.funding import FundingCurve
from src.risk.manager import RiskManager, RiskSnapshot


def test_risk_manager_blocks_spread_and_recommends_reduce_only() -> None:
    manager = RiskManager()
    gate_state = GateState()
    gate_state.market.spread.state = "block"
    gate_state.market.spread.reason = "wide_spread"

    decision = manager.evaluate_ticket(gate_state=gate_state)

    assert decision.allowed is False
    assert decision.reduce_only is True
    assert decision.board_mode == "guarded"
    assert decision.exit_code == 62
    assert decision.reason == "wide_spread"
    assert decision.kill_switch_state == "none"


def test_risk_manager_hard_stop_disallows_tickets() -> None:
    manager = RiskManager()

    decision = manager.evaluate_ticket(kill_switch_state="hard_stop")

    assert decision.allowed is False
    assert decision.board_mode == "halted"
    assert decision.exit_code == 63


def test_risk_manager_respects_reduce_only_assessment() -> None:
    manager = RiskManager()
    snapshot = RiskSnapshot(exposure_r_eff=2.1)
    assessment = manager.evaluate(snapshot)

    decision = manager.evaluate_ticket(assessment=assessment)

    assert decision.reduce_only is True
    assert decision.board_mode == "guarded"
    assert decision.exit_code == 21
    assert decision.kill_switch_state == "none"


def test_risk_manager_reduce_only_advisor_hook() -> None:
    def advisor(_gate_state, _assessment, _spread_status, _kill_switch_state):
        return True, "latency_fallback"

    manager = RiskManager(reduce_only_advisor=advisor)

    decision = manager.evaluate_ticket()

    assert decision.reduce_only is True
    assert decision.board_mode == "guarded"
    assert decision.exit_code == 21
    assert decision.reason == "latency_fallback"


def test_risk_manager_from_policy_and_funding_curve(tmp_path) -> None:
    policy_path = tmp_path / "risk_policy.yaml"
    policy_path.write_text(
        """
schema_version: 1
profiles:
  m1_baseline:
    risk_limits:
      exposure_r_eff_soft_stop: 1.5
      exposure_r_eff_hard_stop: 2.2
    kill_switch:
      drawdown_threshold_pct:
        daily: 1.0
        weekly: 2.0
      capital_floor_pct_of_base: 75
""",
        encoding="utf-8",
    )
    curve = FundingCurve(points={date(2025, 1, 1): -0.2})
    manager = RiskManager.from_policy(path=policy_path, funding_curve=curve)
    snapshot = RiskSnapshot(
        daily_drawdown_pct=1.1,
        exposure_r_eff=1.6,
        session_date=date(2025, 1, 1),
    )
    assessment = manager.evaluate(snapshot)
    assert assessment.kill_switch_suggestion == "soft_stop"
    assert assessment.kill_switch_reason == "daily_drawdown"
    assert assessment.funding_rate == -0.2
