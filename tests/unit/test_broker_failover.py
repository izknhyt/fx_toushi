from __future__ import annotations

from pathlib import Path

from src.brokers.failover import ApiFailoverPlanner


def test_failover_planner_creates_plan(tmp_path: Path) -> None:
    planner = ApiFailoverPlanner(
        state_path=tmp_path / "failover_state.json",
        log_path=tmp_path / "failover_log.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
    )
    plan = planner.plan(reason="latency_spike")
    assert plan.plan_id.startswith("failover-")
    assert plan.trigger_reason == "latency_spike"
    assert plan.actions
    assert plan.manual_steps


def test_failover_dispatch_writes_state(tmp_path: Path) -> None:
    state_path = tmp_path / "failover_state.json"
    planner = ApiFailoverPlanner(
        state_path=state_path,
        log_path=tmp_path / "failover_log.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
    )
    plan = planner.plan(reason="broker_latency")
    result = planner.dispatch(plan, simulate=True)
    assert result["status"] == "simulated"
    assert state_path.exists()
