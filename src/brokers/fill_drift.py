"""Fill drift detector stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class FillDriftEvent:
    order_id: str
    drift_bps: float


class FillDriftDetector:
    def detect(self, fills: Iterable[FillDriftEvent]) -> list[FillDriftEvent]:
        return [event for event in fills if abs(event.drift_bps) >= 1.0]


__all__ = ["FillDriftDetector", "FillDriftEvent"]
