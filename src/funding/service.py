"""Funding curve service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class FundingCurve:
    points: Mapping[date, float] = field(default_factory=dict)
    swap_rates: Mapping[str, "SwapRate"] = field(default_factory=dict)

    def rate_on(self, session_date: date) -> float:
        return float(self.points.get(session_date, 0.0))

    def swap_penalty(self, *, pair: str, direction: str, session_date: date) -> float:
        rate = self.swap_rate(pair=pair, direction=direction)
        if rate == 0.0:
            return 0.0
        triple_day = self.swap_rates.get(pair).triple_day if pair in self.swap_rates else None
        if _is_triple_day(session_date, triple_day):
            return rate * 3
        return rate

    def swap_rate(self, *, pair: str, direction: str) -> float:
        entry = self.swap_rates.get(pair)
        if entry is None:
            return 0.0
        if direction.lower() in {"long", "buy"}:
            return entry.swap_long
        return entry.swap_short


@dataclass(slots=True)
class SwapRate:
    pair: str
    swap_long: float
    swap_short: float
    triple_day: str | None = None
    rollover_time_utc: str | None = None
    last_verified_at: str | None = None
    data_source: str | None = None


class FundingService:
    def __init__(self, curve: FundingCurve | None = None) -> None:
        self._curve = curve or FundingCurve(points={})

    def rate_on(self, session_date: date) -> float:
        return self._curve.rate_on(session_date)

    def swap_penalty(self, *, pair: str, direction: str, session_date: date) -> float:
        return self._curve.swap_penalty(pair=pair, direction=direction, session_date=session_date)


def _is_triple_day(session_date: date, triple_day: str | None) -> bool:
    if not triple_day:
        return False
    day = triple_day.strip().lower()[:3]
    weekday = session_date.weekday()
    mapping = {
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
    }
    return mapping.get(day) == weekday


__all__ = ["FundingCurve", "FundingService", "SwapRate"]
