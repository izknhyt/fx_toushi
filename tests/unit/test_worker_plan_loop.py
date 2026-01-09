"""Tests for worker polling loop wiring."""

from __future__ import annotations

from collections import deque

from src.data.service import WorkerPlan, run_worker_plan


def test_run_worker_plan_drains_queue_with_limits() -> None:
    calls: list[int] = []

    def make_job(idx: int):
        return lambda: calls.append(idx)

    work = deque(make_job(i) for i in range(5))
    sleeps: list[float] = []
    plan = WorkerPlan(provider="primary", stage="stage1", poll_interval_sec=0.1, max_workers=2)

    result = run_worker_plan(
        plan=plan,
        task=None,
        queue=work,
        iterations=10,
        sleep_fn=lambda sec: sleeps.append(sec),
        stop_when_empty=True,
    )

    assert calls == list(range(5))
    assert result["calls"] == 5
    assert result["polls"] == 3
    assert result["sleep_calls"] == 2
    assert all(abs(sec - plan.poll_interval_sec) < 1e-9 for sec in sleeps)


def test_run_worker_plan_executes_default_task_when_no_queue() -> None:
    calls = 0

    def job():
        nonlocal calls
        calls += 1

    sleeps: list[float] = []
    plan = WorkerPlan(provider="secondary", stage="stage0", poll_interval_sec=0.2, max_workers=3)

    result = run_worker_plan(
        plan=plan, task=job, iterations=2, sleep_fn=lambda sec: sleeps.append(sec)
    )

    assert calls == 6
    assert result["polls"] == 2
    assert result["sleep_calls"] == 2
    assert len(sleeps) == 2
