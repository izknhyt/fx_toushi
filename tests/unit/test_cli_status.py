"""Tests for the ``tradectl status`` helper."""

from __future__ import annotations

import json
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

    payload = status(
        monitor=monitor,
        gate_state=gate_state,
        snapshot_manager=_SnapshotManagerStub(),
        kill_switch_state_path=None,
    )

    assert payload["exit_code"] == 62
    guardrails = payload["guardrails"]
    assert guardrails["board_mode"] == "guarded"
    assert guardrails["kill_switch_state"] == "soft_stop"
    assert payload["health"]["status"] == "degraded"
    assert payload["kill_switch"]["state"] == "soft_stop"
    assert payload["kill_switch"]["reason"] == "weekly_drawdown"
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


def test_status_includes_auto_ack_required(tmp_path: Path) -> None:
    monitor = HealthMonitor()
    gate_state = GateState()
    kill_switch_state_path = tmp_path / "kill_switch_state.json"
    kill_switch_state_path.write_text(
        json.dumps({"state": "soft_stop", "reason": "drawdown", "auto_ack_required": True}),
        encoding="utf-8",
    )

    payload = status(
        monitor=monitor,
        gate_state=gate_state,
        kill_switch_state_path=kill_switch_state_path,
    )

    assert payload["kill_switch"]["auto_ack_required"] is True


def test_status_banner_shown_when_reduce_only_active() -> None:
    monitor = HealthMonitor()  # defaults to status="ok"
    gate_state = GateState()
    gate_state.risk.reduce_only = True
    gate_state.risk.reduce_only_reason = "spread_watch"

    payload = status(monitor=monitor, gate_state=gate_state)

    assert payload["exit_code"] == 21
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
    assert actions["ack"]["requested"] is True
    assert actions["ack"]["reference"] == "RUN-DATA-05#step2"
    assert actions["ack"]["status"] == "queued"
    assert actions["ack"]["result"]["status"] == "not_found"
    assert actions["kill_switch"]["requested"] is True
    assert actions["kill_switch"]["requested_state"] == "soft_stop"
    assert actions["board"]["reference"] == "guarded"


def test_status_marks_auto_execute_forced_off(tmp_path: Path) -> None:
    monitor = HealthMonitor()
    gate_state = GateState()
    gate_state.auto_execute = True
    gate_state.risk.reduce_only = True  # force auto_execute to false
    metrics_path = tmp_path / "guardrails.jsonl"

    payload = status(
        monitor=monitor,
        gate_state=gate_state,
        metrics_path=metrics_path,
        actor="tester",
    )

    assert payload["gate"]["auto_execute"] is False
    content = metrics_path.read_text(encoding="utf-8")
    assert "auto_execute_forced_off" in content


def test_status_includes_time_sync_payload(tmp_path: Path) -> None:
    monitor = HealthMonitor()
    gate_state = GateState()
    metrics_path = tmp_path / "guardrails.jsonl"
    time_sync_metrics = tmp_path / "time_sync.jsonl"
    payload = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "clock_drift_ms": 700,
        "status": "ok",
    }
    time_sync_metrics.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    result = status(
        monitor=monitor,
        gate_state=gate_state,
        metrics_path=metrics_path,
        time_sync_check=True,
        time_sync_metrics_path=time_sync_metrics,
    )

    assert result["time_sync"]["status"] == "warn"
    assert result["guardrails"]["time_sync"]["status"] == "warn"
    content = metrics_path.read_text(encoding="utf-8")
    assert "time_sync_status" in content
