"""Guardrail snapshot tests for :mod:`src.core.health`."""

from __future__ import annotations

from src.core.gate import GateState
from src.core.health import HealthMonitor


def test_guardrail_snapshot_combines_health_and_gate_state() -> None:
    monitor = HealthMonitor()
    monitor.raise_condition("warning", "data_latency")
    monitor.suggest_guarded(reason="data_latency", runbook="RUN-DATA-05")

    gate = GateState()
    gate.market.spread.state = "cooldown"
    gate.market.spread.reason = "wide_spread"
    gate.risk.reduce_only = True
    gate.risk.reduce_only_reason = "r_eff_soft_stop"

    snapshot = monitor.guardrail_snapshot(gate)

    assert snapshot.board_mode == "guarded"
    assert snapshot.spread_status == "cooldown"
    assert snapshot.exit_code == 21
    assert "spread:wide_spread" in snapshot.reasons
    assert "reduce_only:r_eff_soft_stop" in snapshot.reasons
    assert snapshot.banner == "data_latency"


def test_guardrail_snapshot_escalates_to_hard_stop() -> None:
    monitor = HealthMonitor()
    monitor.raise_condition("hard_stop", "drawdown")

    gate = GateState()
    gate.risk.kill_switch_recommendation = "hard_stop"
    gate.risk.kill_switch_reason = "drawdown"

    snapshot = monitor.guardrail_snapshot(gate, kill_switch_state="hard_stop")

    assert snapshot.board_mode == "halted"
    assert snapshot.kill_switch_state == "hard_stop"
    assert snapshot.exit_code == 63
