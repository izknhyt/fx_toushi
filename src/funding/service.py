"""Funding curve service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class FundingCurve:
    points: Mapping[date, float]


class FundingService:
    def __init__(self, curve: FundingCurve | None = None) -> None:
        self._curve = curve or FundingCurve(points={})

    def rate_on(self, session_date: date) -> float:
        return float(self._curve.points.get(session_date, 0.0))


__all__ = ["FundingCurve", "FundingService"]
