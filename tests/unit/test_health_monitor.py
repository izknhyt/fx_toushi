"""Unit tests for :mod:`src.core.health`."""

from __future__ import annotations

from src.core.health import HealthMonitor


def test_raise_and_clear_updates_status() -> None:
    monitor = HealthMonitor()

    monitor.raise_condition(
        "degraded",
        "data_latency",
        detail="fetch_p95_exceeded",
        recommended_action="runbook:RUN-DATA-05#enter_guarded",
    )

    snapshot = monitor.snapshot()
    assert snapshot.status == "degraded"
    assert snapshot.reasons[0].code == "data_latency"
    assert snapshot.board_mode_suggestion is None

    monitor.suggest_guarded(reason="data_latency", runbook="docs/runbooks/RUN-DATA-05.md")
    snapshot_with_suggestion = monitor.snapshot()
    assert snapshot_with_suggestion.board_mode_suggestion == "data_latency"

    monitor.clear("data_latency")
    cleared = monitor.snapshot()
    assert cleared.status == "ok"
    assert cleared.reasons == []


def test_kill_switch_suggestion() -> None:
    monitor = HealthMonitor()
    monitor.raise_condition("soft_stop", "weekly_drawdown")
    monitor.suggest_kill_switch(state="soft_stop", reason="weekly_drawdown", runbook="docs/runbooks/RUN-RISK-01.md")

    snapshot = monitor.snapshot()
    assert snapshot.status == "soft_stop"
    assert snapshot.kill_switch is not None
    assert snapshot.kill_switch.state == "soft_stop"
    assert snapshot.kill_switch.reason == "weekly_drawdown"
