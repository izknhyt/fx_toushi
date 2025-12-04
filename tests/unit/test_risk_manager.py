"""Risk manager guardrail evaluation tests."""

from __future__ import annotations

from src.core.gate import GateState
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
