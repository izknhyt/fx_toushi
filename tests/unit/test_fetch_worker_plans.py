"""Tests for applying WorkerPlan to fetch queues."""

from __future__ import annotations

from collections import deque

from src.data.service import WorkerPlan, run_fetch_workers


def test_run_fetch_workers_respects_provider_and_limits() -> None:
    calls: list[str] = []

    def make_job(label: str):
        return lambda: calls.append(label)

    queue = deque(
        [
            ("primary", make_job("p1-1")),
            ("secondary", make_job("s-1")),
            ("primary", make_job("p1-2")),
            ("secondary", make_job("s-2")),
        ]
    )
    sleeps: list[float] = []
    plans = [
        WorkerPlan(provider="primary", stage="stage1", poll_interval_sec=0.05, max_workers=1),
        WorkerPlan(provider="secondary", stage="stage0", poll_interval_sec=0.1, max_workers=2),
    ]

    results = run_fetch_workers(
        plans=plans,
        queue=queue,
        iterations=3,
        sleep_fn=lambda sec: sleeps.append(sec),
        stop_when_empty=True,
    )

    assert calls == ["p1-1", "p1-2", "s-1", "s-2"]
    primary_result = next(r for r in results if r["provider"] == "primary")
    secondary_result = next(r for r in results if r["provider"] == "secondary")
    assert primary_result["calls"] == 2
    assert secondary_result["calls"] == 2
    assert primary_result["polls"] <= 3
    assert secondary_result["polls"] <= 3
    assert sleeps  # at least one sleep invoked according to poll interval
