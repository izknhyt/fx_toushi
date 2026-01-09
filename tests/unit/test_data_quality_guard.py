from __future__ import annotations

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
