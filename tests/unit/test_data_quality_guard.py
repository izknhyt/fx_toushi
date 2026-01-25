from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.data.quality import DataQualityGuard
from src.data.service import MarketFrame


def _frame(symbol: str, close_values: list[float]) -> MarketFrame:
    bars = []
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for idx, close in enumerate(close_values):
        bars.append(
            {
                "timestamp": (now + timedelta(minutes=5 * idx)).isoformat(),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1,
            }
        )
    return MarketFrame(symbol=symbol, timeframe="5m", bars=bars)


def test_compare_detects_drift() -> None:
    guard = DataQualityGuard(expected_timeframe_minutes=5)
    current = _frame("EURUSD", [1.0, 1.1, 1.2, 1.3])
    reference = _frame("EURUSD", [0.5, 0.5, 0.5, 0.5])
    guard.validate(current)

    comparison = guard.compare([reference])

    assert comparison.drift_detected is True
    assert comparison.status == "drift"

def test_compare_requires_matching_reference() -> None:
    guard = DataQualityGuard(expected_timeframe_minutes=5)
    current = _frame("EURUSD", [1.0, 1.1])
    reference = _frame("USDJPY", [1.0, 1.1])
    guard.validate(current)

    comparison = guard.compare([reference])

    assert comparison.status == "error"
    assert "reference_mismatch" in comparison.issues


def test_annotate_writes_payload(tmp_path: Path) -> None:
    guard = DataQualityGuard(expected_timeframe_minutes=5)
    frame = _frame("USDJPY", [150.0, 150.1, 150.2])
    guard.validate(frame)

    out_path = tmp_path / "annotations.jsonl"
    payload = guard.annotate({"note": "quality_check"}, out=out_path)

    assert payload["status"] in {"ok", "warn", "fail"}
    assert payload["symbol"] == "USDJPY"
    assert payload["timeframe"] == "5m"
    assert out_path.exists()
