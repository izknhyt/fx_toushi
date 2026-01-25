from __future__ import annotations

from datetime import date

from src.backtest.walkforward import build_plan, build_plan_from_specs


def test_build_plan_creates_train_and_test_windows() -> None:
    plan = build_plan(
        date(2024, 1, 1),
        date(2024, 2, 15),
        train_days=20,
        test_days=10,
        step_days=10,
    )

    assert plan.segments
    first = plan.segments[0]
    assert first.train_start == date(2024, 1, 1)
    assert first.train_end == date(2024, 1, 21)
    assert first.test_start == first.train_end
    assert first.test_end == date(2024, 1, 31)


def test_build_plan_from_specs_parses_days_and_weeks() -> None:
    plan = build_plan_from_specs(
        start=date(2024, 1, 1),
        end=date(2024, 3, 1),
        window_spec="30d",
        step_spec="2w",
    )

    assert plan.segments
    assert plan.segments[0].train_end == date(2024, 1, 31)
    assert plan.segments[0].test_end == date(2024, 2, 14)
