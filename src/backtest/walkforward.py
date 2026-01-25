"""Walk-forward planning utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from re import match


@dataclass(slots=True)
class WalkForwardSegment:
    index: int
    train_start: date
    train_end: date
    test_end: date

    @property
    def test_start(self) -> date:
        return self.train_end


@dataclass(slots=True)
class WalkForwardPlan:
    segments: list[WalkForwardSegment]


def build_plan(
    start: date,
    end: date,
    *,
    window_days: int = 30,
    step_days: int = 7,
    train_days: int | None = None,
    test_days: int | None = None,
) -> WalkForwardPlan:
    segments: list[WalkForwardSegment] = []
    cursor = start
    index = 1
    train_window = train_days if train_days is not None else window_days
    test_window = test_days if test_days is not None else step_days
    while cursor < end:
        train_end = cursor + timedelta(days=train_window)
        if train_end >= end:
            break
        test_end = min(train_end + timedelta(days=test_window), end)
        if test_end <= train_end:
            break
        segments.append(
            WalkForwardSegment(
                index=index,
                train_start=cursor,
                train_end=train_end,
                test_end=test_end,
            )
        )
        index += 1
        cursor += timedelta(days=step_days)
    return WalkForwardPlan(segments=segments)


def build_plan_from_specs(
    *,
    start: date,
    end: date,
    window_spec: str,
    step_spec: str,
) -> WalkForwardPlan:
    train_days = _parse_window_spec(window_spec)
    test_days = _parse_window_spec(step_spec)
    return build_plan(
        start,
        end,
        train_days=train_days,
        test_days=test_days,
        step_days=test_days,
    )


def _parse_window_spec(spec: str) -> int:
    parsed = match(r"^(\d+)([dw])$", spec.strip().lower())
    if parsed:
        value = int(parsed.group(1))
        unit = parsed.group(2)
        if unit == "d":
            return value
        if unit == "w":
            return value * 7
    parsed = match(r"^(\d+)(m)$", spec.strip().lower())
    if parsed:
        value = int(parsed.group(1))
        return value * 30
    raise ValueError(f"Unsupported window spec: {spec}")


__all__ = ["WalkForwardPlan", "WalkForwardSegment", "build_plan", "build_plan_from_specs"]
