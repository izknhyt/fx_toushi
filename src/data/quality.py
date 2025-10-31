"""Data quality guard scaffolding.

The stub mirrors the interfaces referenced in detailed_design_fx_signal_tool_v1.md
§3.2 and adds helpers for Manual CSV verification metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import json
from datetime import datetime, timezone

from .service import MarketFrame

__all__ = ["DataQualityGuard", "QualityResult"]


@dataclass(slots=True)
class QualityResult:
    """Placeholder result returned by :class:`DataQualityGuard`."""

    status: str
    issues: list[str]
    recommended_action: str | None = None


class DataQualityGuard:
    """Minimal stub of the quality guard described in §3.2."""

    def __init__(self) -> None:
        self._issues: list[str] = []

    def validate(self, frame: MarketFrame) -> QualityResult:
        """Validate a market frame and return a placeholder result."""

        return QualityResult(status="unknown", issues=list(self._issues))

    def report(self, *, out: Path | None = None) -> dict[str, Any]:
        """Return a dummy quality report payload."""

        report = {"status": "noop", "issues": list(self._issues)}
        if out is not None:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        return report

    def compare(self, reference_series: Iterable[MarketFrame]) -> QualityResult:
        """Compare frames to a reference series."""

        _ = list(reference_series)  # materialise for deterministic behaviour
        return QualityResult(status="unimplemented", issues=list(self._issues))

    def record_manual_csv_hash_verification(
        self,
        *,
        hash_value: str,
        symbol: str,
        timeframe: str,
        reviewer: str,
        metrics_path: Path,
    ) -> None:
        """Append a JSONL record documenting manual CSV hash verification.

        The method enables tests to exercise the manual ingestion audit flow
        described in §3.1 without requiring a full metrics pipeline.  The file is
        created when absent and appended otherwise.
        """

        record = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "symbol": symbol,
            "timeframe": timeframe,
            "hash": hash_value,
            "reviewer": reviewer,
        }
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
