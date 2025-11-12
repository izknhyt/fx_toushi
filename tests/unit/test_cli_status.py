"""Tests for the ``tradectl status`` helper."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.core.gate import GateState
from src.core.health import HealthMonitor
from src.core.snapshot import SnapshotManager, SnapshotRestoreResult
from src.interfaces.cli.status import status


class _SnapshotManagerStub(SnapshotManager):
    def __init__(self) -> None:
        super().__init__(base_path=Path("snapshots/tests"))

    def restore(self, path=None) -> SnapshotRestoreResult:  # type: ignore[override]
        return SnapshotRestoreResult(
            state={"session": "backtest", "id": "session-123"},
            warnings=("stale_snapshot",),
        )


def test_status_returns_health_and_kill_switch_snapshot() -> None:
    monitor = HealthMonitor()
    monitor.raise_condition("degraded", "data_latency")
    monitor.suggest_guarded(reason="data_latency", runbook="docs/runbooks/RUN-DATA-05.md")
    monitor.suggest_kill_switch(state="soft_stop", reason="weekly_drawdown")

    gate_state = GateState()
    gate_state.risk.kill_switch_recommendation = "soft_stop"
    gate_state.risk.kill_switch_reason = "weekly_drawdown"

    payload = status(monitor=monitor, gate_state=gate_state, snapshot_manager=_SnapshotManagerStub())

    assert payload["health"]["status"] == "degraded"
    assert payload["kill_switch"] == {
        "suggestion": "soft_stop",
        "reason": "weekly_drawdown",
        "requested_transition": None,
    }
    snapshots = payload["snapshots"]
    assert snapshots["status"] == "ok"
    assert snapshots["state"] == {"session": "backtest", "id": "session-123"}
    assert snapshots["warnings"] == ["stale_snapshot"]
    assert snapshots["base_path"].endswith("snapshots/tests")
    banner = payload["ops"]["banner"]
    assert banner is not None
    assert banner["kind"] == "acceptable_degradation"
    assert banner["runbook"] == "docs/runbooks/RUN-DATA-05.md"
    actions = payload["ops"]["actions"]
    assert actions["ack"]["status"] == "idle"
    assert actions["kill_switch"]["status"] == "idle"
    assert actions["board"]["status"] == "idle"


def test_status_banner_shown_when_reduce_only_active() -> None:
    monitor = HealthMonitor()  # defaults to status="ok"
    gate_state = GateState()
    gate_state.risk.reduce_only = True
    gate_state.risk.reduce_only_reason = "spread_watch"

    payload = status(monitor=monitor, gate_state=gate_state)

    banner = payload["ops"]["banner"]
    assert banner is not None
    assert banner["kind"] == "acceptable_degradation"
    assert banner["reduce_only"] is True
    assert banner["severity"] == "ok"


def test_status_tracks_ops_action_requests() -> None:
    monitor = HealthMonitor()
    gate_state = GateState()
    deadline = datetime.now(timezone.utc)
    gate_state.human.double_entry_required = True
    gate_state.human.required_roles = ["ops_lead"]
    gate_state.human.acknowledged_roles = []
    gate_state.human.ack_deadline = deadline

    payload = status(
        monitor=monitor,
        gate_state=gate_state,
        ack="RUN-DATA-05#step2",
        kill_switch="soft_stop",
        board="guarded",
    )

    actions = payload["ops"]["actions"]
    assert actions["ack"] == {"requested": True, "reference": "RUN-DATA-05#step2", "status": "queued"}
    assert actions["kill_switch"]["requested"] is True
    assert actions["board"]["reference"] == "guarded"
