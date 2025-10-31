"""Tests for the ``tradectl status`` helper."""

from __future__ import annotations

from src.core.gate import GateState
from src.core.health import HealthMonitor
from src.interfaces.cli.status import status


def test_status_returns_health_and_kill_switch_snapshot() -> None:
    monitor = HealthMonitor()
    monitor.raise_condition("degraded", "data_latency")
    monitor.suggest_guarded(reason="data_latency", runbook="docs/runbooks/RUN-DATA-05.md")
    monitor.suggest_kill_switch(state="soft_stop", reason="weekly_drawdown")

    gate_state = GateState()
    gate_state.risk.kill_switch_recommendation = "soft_stop"
    gate_state.risk.kill_switch_reason = "weekly_drawdown"

    payload = status(monitor=monitor, gate_state=gate_state)

    assert payload["health"]["status"] == "degraded"
    assert payload["kill_switch"] == {
        "suggestion": "soft_stop",
        "reason": "weekly_drawdown",
        "requested_transition": None,
    }
    assert payload["risk"]["reduce_only"] is False
    banner = payload["ops"]["banner"]
    assert banner is not None
    assert banner["kind"] == "acceptable_degradation"
    assert banner["runbook"] == "docs/runbooks/RUN-DATA-05.md"
