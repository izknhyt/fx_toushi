"""Fill drift detector stub."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(slots=True)
class FillDriftEvent:
    order_id: str
    drift_bps: float


class FillDriftDetector:
    def detect(self, fills: Iterable[FillDriftEvent]) -> list[FillDriftEvent]:
        return [event for event in fills if abs(event.drift_bps) >= 1.0]


__all__ = ["FillDriftDetector", "FillDriftEvent"]
