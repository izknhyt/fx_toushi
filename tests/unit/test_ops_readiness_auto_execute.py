from __future__ import annotations

import pytest

from src.core.gate import GateAggregator, GateState
from src.interfaces.cli import ops
from src.ops.profit_readiness import EXIT_GUARDED, EXIT_OK, ProfitReadinessError, ProfitReadinessResult


def test_readiness_enables_auto_execute_on_success(monkeypatch, tmp_path) -> None:
    result = ProfitReadinessResult(
        status="ok",
        exit_code=EXIT_OK,
        metrics={"auto_execute_ready": True},
        sample_count=30,
        evidence=["scoreboard/bridge/latest.json"],
        watchlist=0,
        stale=[],
    )
    monkeypatch.setattr(ops, "verify_profit_readiness", lambda **kwargs: result)

    gate_path = tmp_path / "gate.json"
    profit_path = tmp_path / "profit.jsonl"
    worklog_path = tmp_path / "ops_worklog.jsonl"

    payload = ops.readiness(
        include_profit=True,
        verify=True,
        require_auto_execute=True,
        profit_path=profit_path,
        gate_state_path=gate_path,
        ops_worklog_path=worklog_path,
        record_actor="tester",
    )

    state = GateState.load(gate_path)
    assert state.auto_execute is True
    assert payload["auto_execute"] is not None and payload["auto_execute"]["changed"] is True
    assert "upgraded" in profit_path.read_text(encoding="utf-8")
    assert "auto_execute_on" in worklog_path.read_text(encoding="utf-8")


def test_readiness_disables_auto_execute_on_failure(monkeypatch, tmp_path) -> None:
    def _fail_verify(**kwargs):
        raise ProfitReadinessError("Hands-off auto_execute criteria not satisfied", exit_code=EXIT_GUARDED)

    monkeypatch.setattr(ops, "verify_profit_readiness", _fail_verify)

    gate_path = tmp_path / "gate.json"
    agg = GateAggregator()
    agg.set_profit_readiness_status("ok", allow_auto_execute=True)
    agg.persist_latest(path=gate_path)

    profit_path = tmp_path / "profit.jsonl"
    worklog_path = tmp_path / "ops_worklog.jsonl"

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
    content = profit_path.read_text(encoding="utf-8")
    assert "downgraded" in content
    assert "auto_execute_off" in worklog_path.read_text(encoding="utf-8")
