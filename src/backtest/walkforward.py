"""Walk-forward planning stub."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(slots=True)
class WalkForwardSegment:
    index: int
    start: date
    end: date


@dataclass(slots=True)
class WalkForwardPlan:
    segments: list[WalkForwardSegment]


def build_plan(
    start: date, end: date, *, window_days: int = 30, step_days: int = 7
) -> WalkForwardPlan:
    segments: list[WalkForwardSegment] = []
    cursor = start
    index = 1
    while cursor < end:
        segment_end = min(cursor + timedelta(days=window_days), end)
        segments.append(WalkForwardSegment(index=index, start=cursor, end=segment_end))
        index += 1
        cursor += timedelta(days=step_days)
    return WalkForwardPlan(segments=segments)


__all__ = ["WalkForwardPlan", "WalkForwardSegment", "build_plan"]
