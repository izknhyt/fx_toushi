"""Data quality guard scaffolding.

The stub mirrors the interfaces referenced in detailed_design_fx_signal_tool_v1.md
§3.2 and adds helpers for Manual CSV verification metrics.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .service import MarketFrame

__all__ = ["DataQualityGuard", "QualityResult", "QualityComparison", "DataLatencyAlert"]

_QUALITY_FLAG_MAP = {
    "missing_bars": 1,
    "dup_bars": 2,
    "out_of_order": 3,
    "ts_mismatch": 4,
}
_QUALITY_FLAG_ALIASES = {
    "empty_bars": "missing_bars",
    "gap_exceeds_threshold": "missing_bars",
    "missing_ratio_high": "missing_bars",
    "timestamp_misaligned": "ts_mismatch",
    "missing_timestamp": "ts_mismatch",
}

DEFAULT_TIME_SYNC_METRICS = Path("metrics/time_sync.jsonl")


@dataclass(slots=True)
class QualityResult:
    """Result returned by :class:`DataQualityGuard`."""

    status: str
    issues: list[str]
    recommended_action: str | None = None
    quality_flag: int = 0
    clock_drift_ms: int | None = None
    missing_ratio: float | None = None


@dataclass(slots=True)
class QualityComparison:
    """Comparison result from reference series checks."""

    status: str
    issues: list[str]
    drift_detected: bool
    diff_stats: dict[str, float]


@dataclass(slots=True, frozen=True)
class DataLatencyAlert:
    """Alert payload emitted when data latency thresholds are breached."""

    symbol: str
    provider: str
    lag_seconds: float
    clock_drift_ms: int | None
    severity: Literal["warn", "major", "critical"]
    manual_csv_required: bool

    def to_event(self) -> dict[str, Any]:
        return {
            "event": "data.latency_alert",
            "symbol": self.symbol,
            "provider": self.provider,
            "lag_seconds": float(self.lag_seconds),
            "clock_drift_ms": self.clock_drift_ms,
            "severity": self.severity,
            "manual_csv_required": self.manual_csv_required,
        }


class DataQualityGuard:
    """Minimal quality checks for M1 ingestion pipelines."""

    def __init__(
        self,
        *,
        expected_timeframe_minutes: int = 5,
        max_gap_minutes: int = 10,
        time_sync_metrics_path: Path = DEFAULT_TIME_SYNC_METRICS,
        ntp_max_ms: int = 50,
        missing_ratio_warn: float = 0.1,
    ) -> None:
        self._issues: list[str] = []
        self.expected_timeframe_minutes = expected_timeframe_minutes
        self.max_gap_minutes = max_gap_minutes
        self.time_sync_metrics_path = time_sync_metrics_path
        self.ntp_max_ms = ntp_max_ms
        self.missing_ratio_warn = missing_ratio_warn
        self._last_result: QualityResult | None = None
        self._last_frame: MarketFrame | None = None

    def validate(self, frame: MarketFrame) -> QualityResult:
        """Validate a market frame and return a quality result."""

        issues: list[str] = []
        clock_drift_ms = _load_latest_clock_drift(self.time_sync_metrics_path)
        if clock_drift_ms is not None and clock_drift_ms > self.ntp_max_ms:
            _append_issue(issues, "ntp_drift")
        if not frame.bars:
            _append_issue(issues, "empty_bars")
            _append_issue(issues, "missing_bars")
            quality_flag = _quality_flag_for_issues(issues)
            frame.quality_flag = quality_flag
            result = self._finalize(
                issues,
                recommended_action="runbook_run_data_05",
                quality_flag=quality_flag,
                clock_drift_ms=clock_drift_ms,
                missing_ratio=None,
            )
            self._last_result = result
            self._last_frame = frame
            return result

        timestamps: list[datetime] = []
        last_seen: datetime | None = None
        for bar in frame.bars:
            ts = _parse_timestamp(bar.get("timestamp") or bar.get("ts"))
            if ts is None:
                _append_issue(issues, "missing_timestamp")
                _append_issue(issues, "ts_mismatch")
                continue
            timestamps.append(ts)
            if last_seen and ts < last_seen:
                _append_issue(issues, "out_of_order")
            last_seen = ts
            if ts.minute % self.expected_timeframe_minutes != 0 or ts.second != 0:
                _append_issue(issues, "timestamp_misaligned")
                _append_issue(issues, "ts_mismatch")
            low = _as_float(bar.get("low"))
            high = _as_float(bar.get("high"))
            open_ = _as_float(bar.get("open"))
            close = _as_float(bar.get("close"))
            if low is None or high is None or open_ is None or close is None:
                _append_issue(issues, "missing_ohlc")
            else:
                if low > min(open_, close) or high < max(open_, close) or low > high:
                    _append_issue(issues, "ohlc_bounds")
            volume = _as_float(bar.get("volume"))
            if volume is not None and volume < 0:
                _append_issue(issues, "negative_volume")

        if timestamps:
            if len(set(timestamps)) != len(timestamps):
                _append_issue(issues, "dup_bars")
            timestamps.sort()
            missing_ratio = _compute_missing_ratio(
                timestamps, expected_minutes=self.expected_timeframe_minutes
            )
            if missing_ratio is not None and missing_ratio > self.missing_ratio_warn:
                _append_issue(issues, "missing_ratio_high")
            for prev, cur in zip(timestamps, timestamps[1:], strict=False):
                gap_minutes = int((cur - prev).total_seconds() // 60)
                if gap_minutes > self.max_gap_minutes:
                    _append_issue(issues, "gap_exceeds_threshold")
                    _append_issue(issues, "missing_bars")
                    break
        else:
            missing_ratio = None

        quality_flag = _quality_flag_for_issues(issues)
        frame.quality_flag = quality_flag
        result = self._finalize(
            issues,
            recommended_action="review_data_quality",
            quality_flag=quality_flag,
            clock_drift_ms=clock_drift_ms,
            missing_ratio=missing_ratio,
        )
        self._last_result = result
        self._last_frame = frame
        return result

    def evaluate(
        self,
        frame: MarketFrame,
        *,
        provider: str,
        lag_seconds: float | None = None,
    ) -> DataLatencyAlert | None:
        """Evaluate data latency and return an alert payload if needed."""

        result = self.validate(frame)
        if result.status == "ok":
            return None

        severity = _resolve_latency_severity(
            lag_seconds=lag_seconds,
            missing_ratio=result.missing_ratio,
            clock_drift_ms=result.clock_drift_ms,
            max_gap_minutes=self.max_gap_minutes,
            missing_ratio_warn=self.missing_ratio_warn,
            ntp_max_ms=self.ntp_max_ms,
        )
        manual_csv_required = result.status == "fail" and provider == "primary"
        return DataLatencyAlert(
            symbol=frame.symbol,
            provider=provider,
            lag_seconds=float(lag_seconds or 0.0),
            clock_drift_ms=result.clock_drift_ms,
            severity=severity,
            manual_csv_required=manual_csv_required,
        )

    def report(self, *, out: Path | None = None) -> dict[str, Any]:
        """Return a quality report payload."""

        result = self._last_result or QualityResult(status="unknown", issues=list(self._issues))
        report = {
            "status": result.status,
            "issues": list(result.issues),
            "recommended_action": result.recommended_action,
            "quality_flag": result.quality_flag,
            "clock_drift_ms": result.clock_drift_ms,
            "missing_ratio": result.missing_ratio,
        }
        if out is not None:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        return report

    def compare(self, reference_series: Iterable[MarketFrame]) -> QualityComparison:
        """Compare the last validated frame to a reference series."""

        reference = list(reference_series)
        if self._last_frame is None:
            return QualityComparison(
                status="error",
                issues=["missing_current_frame"],
                drift_detected=False,
                diff_stats={},
            )
        if not reference:
            return QualityComparison(
                status="error",
                issues=["reference_missing"],
                drift_detected=False,
                diff_stats={},
            )
        reference_frame = reference[-1]
        if (
            reference_frame.symbol != self._last_frame.symbol
            or reference_frame.timeframe != self._last_frame.timeframe
        ):
            return QualityComparison(
                status="error",
                issues=["reference_mismatch"],
                drift_detected=False,
                diff_stats={},
            )
        current_stats = _compute_bar_stats(self._last_frame.bars)
        reference_stats = _compute_bar_stats(reference_frame.bars)
        diff_stats = _compare_stats(current_stats, reference_stats)
        drift_detected = diff_stats.get("mean_diff_ratio", 0.0) >= 0.05 or diff_stats.get(
            "std_diff_ratio", 0.0
        ) >= 0.5
        status = "drift" if drift_detected else "ok"
        return QualityComparison(
            status=status,
            issues=[] if status == "ok" else ["drift_detected"],
            drift_detected=drift_detected,
            diff_stats=diff_stats,
        )

    def annotate(
        self,
        event: dict[str, Any],
        *,
        out: Path = Path("reports") / "quality" / "annotations.jsonl",
    ) -> dict[str, Any]:
        """Append a quality annotation record for external consumers."""

        symbol = self._last_frame.symbol if self._last_frame else None
        timeframe = self._last_frame.timeframe if self._last_frame else None
        payload = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "event": event,
            "status": self._last_result.status if self._last_result else "unknown",
            "issues": list(self._last_result.issues) if self._last_result else [],
            "quality_flag": self._last_result.quality_flag if self._last_result else 0,
            "symbol": symbol,
            "timeframe": timeframe,
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return payload

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

    def _finalize(
        self,
        issues: list[str],
        *,
        recommended_action: str | None,
        quality_flag: int = 0,
        clock_drift_ms: int | None = None,
        missing_ratio: float | None = None,
    ) -> QualityResult:
        if not issues:
            status = "ok"
        elif issues == ["empty_bars"] or issues == ["empty_bars", "missing_bars"]:
            status = "warn"
        else:
            status = "fail"
        return QualityResult(
            status=status,
            issues=issues,
            recommended_action=recommended_action,
            quality_flag=quality_flag,
            clock_drift_ms=clock_drift_ms,
            missing_ratio=missing_ratio,
        )


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _compute_bar_stats(bars: list[dict[str, object]]) -> dict[str, float]:
    closes: list[float] = []
    for bar in bars:
        close = _as_float(bar.get("close"))
        if close is not None:
            closes.append(close)
    if not closes:
        return {"count": 0.0, "mean_close": 0.0, "std_close": 0.0}
    mean = sum(closes) / len(closes)
    variance = sum((value - mean) ** 2 for value in closes) / len(closes)
    return {"count": float(len(closes)), "mean_close": mean, "std_close": math.sqrt(variance)}


def _compare_stats(current: dict[str, float], reference: dict[str, float]) -> dict[str, float]:
    mean_ref = reference.get("mean_close", 0.0)
    std_ref = reference.get("std_close", 0.0)
    mean_cur = current.get("mean_close", 0.0)
    std_cur = current.get("std_close", 0.0)
    mean_diff_ratio = abs(mean_cur - mean_ref) / max(abs(mean_ref), 1e-6)
    std_diff_ratio = abs(std_cur - std_ref) / max(abs(std_ref), 1e-6)
    return {
        "mean_diff_ratio": mean_diff_ratio,
        "std_diff_ratio": std_diff_ratio,
        "current_mean": mean_cur,
        "reference_mean": mean_ref,
    }


def _load_latest_clock_drift(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        drift = payload.get("clock_drift_ms")
        if drift is None:
            continue
        try:
            return int(round(float(drift)))
        except (TypeError, ValueError):
            continue
    return None


def _compute_missing_ratio(
    timestamps: list[datetime], *, expected_minutes: int
) -> float | None:
    if not timestamps:
        return None
    if expected_minutes <= 0:
        return None
    start = timestamps[0]
    end = timestamps[-1]
    delta_minutes = int((end - start).total_seconds() // 60)
    expected = (delta_minutes // expected_minutes) + 1
    if expected <= 0:
        return None
    missing = max(expected - len(set(timestamps)), 0)
    return missing / expected


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _append_issue(issues: list[str], issue: str) -> None:
    if issue not in issues:
        issues.append(issue)


def _quality_flag_for_issues(issues: list[str]) -> int:
    if not issues:
        return 0
    flags: list[int] = []
    for issue in issues:
        key = _QUALITY_FLAG_ALIASES.get(issue, issue)
        flag = _QUALITY_FLAG_MAP.get(key)
        if flag is not None:
            flags.append(flag)
    return max(flags, default=0)


def _resolve_latency_severity(
    *,
    lag_seconds: float | None,
    missing_ratio: float | None,
    clock_drift_ms: int | None,
    max_gap_minutes: int,
    missing_ratio_warn: float,
    ntp_max_ms: int,
) -> Literal["warn", "major", "critical"]:
    severity = "warn"
    severity_rank = {"warn": 0, "major": 1, "critical": 2}

    def _promote(candidate: str) -> None:
        nonlocal severity
        if severity_rank[candidate] > severity_rank[severity]:
            severity = candidate

    if lag_seconds is not None:
        major_threshold = max_gap_minutes * 60
        critical_threshold = max_gap_minutes * 120
        if lag_seconds >= critical_threshold:
            _promote("critical")
        elif lag_seconds >= major_threshold:
            _promote("major")

    if missing_ratio is not None and missing_ratio_warn > 0:
        major_ratio = min(missing_ratio_warn * 2, 1.0)
        critical_ratio = min(missing_ratio_warn * 3, 1.0)
        if missing_ratio >= critical_ratio:
            _promote("critical")
        elif missing_ratio >= major_ratio:
            _promote("major")
        elif missing_ratio >= missing_ratio_warn:
            _promote("warn")

    if clock_drift_ms is not None and ntp_max_ms > 0:
        if clock_drift_ms >= ntp_max_ms * 3:
            _promote("critical")
        elif clock_drift_ms >= ntp_max_ms * 2:
            _promote("major")
        elif clock_drift_ms >= ntp_max_ms:
            _promote("warn")

    return severity
