"""Data quality guard scaffolding.

The stub mirrors the interfaces referenced in detailed_design_fx_signal_tool_v1.md
§3.2 and adds helpers for Manual CSV verification metrics.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .service import MarketFrame

__all__ = ["DataQualityGuard", "QualityResult"]


@dataclass(slots=True)
class QualityResult:
    """Result returned by :class:`DataQualityGuard`."""

    status: str
    issues: list[str]
    recommended_action: str | None = None


class DataQualityGuard:
    """Minimal quality checks for M1 ingestion pipelines."""

    def __init__(
        self,
        *,
        expected_timeframe_minutes: int = 5,
        max_gap_minutes: int = 10,
    ) -> None:
        self._issues: list[str] = []
        self.expected_timeframe_minutes = expected_timeframe_minutes
        self.max_gap_minutes = max_gap_minutes
        self._last_result: QualityResult | None = None

    def validate(self, frame: MarketFrame) -> QualityResult:
        """Validate a market frame and return a quality result."""

        issues: list[str] = []
        if not frame.bars:
            issues.append("empty_bars")
            result = self._finalize(issues, recommended_action="runbook_run_data_05")
            self._last_result = result
            return result

        timestamps: list[datetime] = []
        for bar in frame.bars:
            ts = _parse_timestamp(bar.get("timestamp") or bar.get("ts"))
            if ts is None:
                issues.append("missing_timestamp")
                continue
            timestamps.append(ts)
            if ts.minute % self.expected_timeframe_minutes != 0:
                issues.append("timestamp_misaligned")
            low = _as_float(bar.get("low"))
            high = _as_float(bar.get("high"))
            open_ = _as_float(bar.get("open"))
            close = _as_float(bar.get("close"))
            if low is None or high is None or open_ is None or close is None:
                issues.append("missing_ohlc")
            else:
                if low > min(open_, close) or high < max(open_, close) or low > high:
                    issues.append("ohlc_bounds")
            volume = _as_float(bar.get("volume"))
            if volume is not None and volume < 0:
                issues.append("negative_volume")

        if timestamps:
            timestamps.sort()
            for prev, cur in zip(timestamps, timestamps[1:], strict=False):
                gap_minutes = int((cur - prev).total_seconds() // 60)
                if gap_minutes > self.max_gap_minutes:
                    issues.append("gap_exceeds_threshold")
                    break

        result = self._finalize(issues, recommended_action="review_data_quality")
        self._last_result = result
        return result

    def report(self, *, out: Path | None = None) -> dict[str, Any]:
        """Return a quality report payload."""

        result = self._last_result or QualityResult(status="unknown", issues=list(self._issues))
        report = {
            "status": result.status,
            "issues": list(result.issues),
            "recommended_action": result.recommended_action,
        }
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

    def _finalize(self, issues: list[str], *, recommended_action: str | None) -> QualityResult:
        if not issues:
            status = "ok"
        elif issues == ["empty_bars"]:
            status = "warn"
        else:
            status = "fail"
        return QualityResult(status=status, issues=issues, recommended_action=recommended_action)


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
