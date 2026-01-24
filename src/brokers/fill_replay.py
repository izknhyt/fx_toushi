"""Replay shadow fills to summarize drift findings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.brokers.fill_drift import FillDriftAlert, FillDriftDetector


class FillReplayError(RuntimeError):
    """Raised when replay fails or violates strict thresholds."""


@dataclass(slots=True)
class FillReplayReport:
    total_records: int
    drift_alerts: list[FillDriftAlert]
    status: str


class FillReplayService:
    def __init__(self, *, detector: FillDriftDetector | None = None) -> None:
        self._detector = detector or FillDriftDetector()

    def replay(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        strict: bool = False,
    ) -> FillReplayReport:
        record_list = list(records)
        alerts = self._detector.detect(record_list)
        status = "ok" if not alerts else "drift_detected"
        report = FillReplayReport(
            total_records=len(record_list),
            drift_alerts=alerts,
            status=status,
        )
        if strict and alerts:
            raise FillReplayError("shadow drift detected during strict replay")
        return report


__all__ = ["FillReplayService", "FillReplayReport", "FillReplayError"]
