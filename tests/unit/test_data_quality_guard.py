from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src.data.quality import DataQualityGuard
from src.data.service import MarketFrame


def _bar(
    ts: datetime, *, o: float, h: float, low: float, c: float, v: float = 1.0
) -> dict[str, object]:
    return {
        "timestamp": ts.isoformat().replace("+00:00", "Z"),
        "open": o,
        "high": h,
        "low": low,
        "close": c,
        "volume": v,
    }


def test_quality_guard_accepts_clean_bars() -> None:
    guard = DataQualityGuard(expected_timeframe_minutes=5, max_gap_minutes=10)
    start = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    bars = [_bar(start + timedelta(minutes=5 * i), o=1, h=2, low=0.5, c=1.5) for i in range(5)]
    frame = MarketFrame(symbol="USDJPY", timeframe="5m", bars=bars)

    result = guard.validate(frame)

    assert result.status == "ok"
    assert result.issues == []


def test_quality_guard_flags_ohlc_bounds() -> None:
    guard = DataQualityGuard(expected_timeframe_minutes=5, max_gap_minutes=10)
    ts = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    bars = [_bar(ts, o=2.0, h=1.0, low=0.5, c=2.5)]
    frame = MarketFrame(symbol="USDJPY", timeframe="5m", bars=bars)

    result = guard.validate(frame)

    assert result.status == "fail"
    assert "ohlc_bounds" in result.issues


def test_quality_guard_flags_gap() -> None:
    guard = DataQualityGuard(expected_timeframe_minutes=5, max_gap_minutes=10)
    start = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    bars = [
        _bar(start, o=1, h=2, low=0.5, c=1.2),
        _bar(start + timedelta(minutes=30), o=1, h=2, low=0.5, c=1.2),
    ]
    frame = MarketFrame(symbol="USDJPY", timeframe="5m", bars=bars)

    result = guard.validate(frame)

    assert result.status == "fail"
    assert "gap_exceeds_threshold" in result.issues


def test_quality_guard_records_ntp_drift_and_missing_ratio(tmp_path) -> None:
    metrics_path = tmp_path / "time_sync.jsonl"
    metrics_path.write_text(json.dumps({"clock_drift_ms": 120}) + "\n", encoding="utf-8")
    guard = DataQualityGuard(
        expected_timeframe_minutes=5,
        max_gap_minutes=30,
        time_sync_metrics_path=metrics_path,
        ntp_max_ms=50,
        missing_ratio_warn=0.1,
    )
    start = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    bars = [
        _bar(start, o=1, h=2, low=0.5, c=1.2),
        _bar(start + timedelta(minutes=5), o=1, h=2, low=0.5, c=1.2),
        _bar(start + timedelta(minutes=15), o=1, h=2, low=0.5, c=1.2),
        _bar(start + timedelta(minutes=20), o=1, h=2, low=0.5, c=1.2),
    ]
    frame = MarketFrame(symbol="USDJPY", timeframe="5m", bars=bars)

    result = guard.validate(frame)

    assert result.clock_drift_ms == 120
    assert result.missing_ratio is not None and result.missing_ratio > 0.1
    assert "ntp_drift" in result.issues
    assert "missing_ratio_high" in result.issues


def test_quality_guard_evaluate_builds_latency_alert(tmp_path) -> None:
    metrics_path = tmp_path / "time_sync.jsonl"
    metrics_path.write_text(json.dumps({"clock_drift_ms": 120}) + "\n", encoding="utf-8")
    guard = DataQualityGuard(
        expected_timeframe_minutes=5,
        max_gap_minutes=30,
        time_sync_metrics_path=metrics_path,
        ntp_max_ms=50,
        missing_ratio_warn=0.1,
    )
    start = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    bars = [
        _bar(start, o=1, h=2, low=0.5, c=1.2),
        _bar(start + timedelta(minutes=5), o=1, h=2, low=0.5, c=1.2),
        _bar(start + timedelta(minutes=15), o=1, h=2, low=0.5, c=1.2),
        _bar(start + timedelta(minutes=20), o=1, h=2, low=0.5, c=1.2),
    ]
    frame = MarketFrame(symbol="USDJPY", timeframe="5m", bars=bars)

    alert = guard.evaluate(frame, provider="primary", lag_seconds=600)

    assert alert is not None
    assert alert.clock_drift_ms == 120
    assert alert.manual_csv_required is True
    assert alert.severity == "major"
