from __future__ import annotations

import pytest

from src.core.gate import GateAggregator, GateState
from src.core.health import HealthMonitor
from src.interfaces.cli.status import status
from src.interfaces.cli import ops
from src.ops.profit_readiness import EXIT_GUARDED, ProfitReadinessError


def test_ops_readiness_and_status_log_auto_execute_forced_off(monkeypatch, tmp_path) -> None:
    gate_path = tmp_path / "gate_state.json"
    profit_path = tmp_path / "profit_readiness.jsonl"
    worklog_path = tmp_path / "ops_worklog.jsonl"
    metrics_path = tmp_path / "guardrails.jsonl"

    agg = GateAggregator()
    agg.set_profit_readiness_status("ok", allow_auto_execute=True)
    agg.persist_latest(path=gate_path)

    def _fail_verify(**kwargs):
        raise ProfitReadinessError("Hands-off auto_execute criteria not satisfied", exit_code=EXIT_GUARDED)

    monkeypatch.setattr(ops, "verify_profit_readiness", _fail_verify)

    with pytest.raises(ProfitReadinessError):
        ops.readiness(
            include_profit=True,
            verify=True,
            require_auto_execute=True,
            profit_path=profit_path,
            gate_state_path=gate_path,
            ops_worklog_path=worklog_path,
            record_actor="tester",
        )

    state = GateState.load(gate_path)
    assert state.auto_execute is False
    assert "downgraded" in profit_path.read_text(encoding="utf-8")
    assert "auto_execute_off" in worklog_path.read_text(encoding="utf-8")

    state.auto_execute = True
    state.risk.reduce_only = True
    state.dump(gate_path)

    monitor = HealthMonitor()
    status(
        monitor=monitor,
        gate_state=state,
        metrics_path=metrics_path,
        actor="tester",
    )

    log = metrics_path.read_text(encoding="utf-8")
    assert "auto_execute_forced_off" in log
