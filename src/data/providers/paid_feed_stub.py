"""Paid feed simulator provider for backtest/paper validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..service import MarketFrame, MarketRequest
from .base import ProviderAdapter

__all__ = ["PaidFeedStubProvider"]


@dataclass(slots=True)
class PaidFeedStubProvider(ProviderAdapter):  # type: ignore[misc]
    """Adapter that loads bars from a paid feed stub CSV."""

    name: str = "paid_feed_stub"
    path: Path = Path("data/paid_feed_stub.csv")

    def fetch_bars(self, request: MarketRequest) -> list[MarketFrame]:
        frame = _load_stub(self.path)
        if frame.empty:
            return [MarketFrame(symbol=symbol, timeframe=request.timeframe, bars=[]) for symbol in request.symbols]

        start = _parse_time(request.start)
        end = _parse_time(request.end)
        if start is not None:
            frame = frame[frame["timestamp"] >= start]
        if end is not None:
            frame = frame[frame["timestamp"] <= end]

        frames: list[MarketFrame] = []
        for symbol in request.symbols:
            symbol_frame = frame[frame["symbol"] == symbol.upper()]
            rows = _frame_to_rows(symbol_frame)
            frames.append(MarketFrame(symbol=symbol, timeframe=request.timeframe, bars=rows))
        return frames


def _load_stub(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if "symbol" not in frame.columns:
        return pd.DataFrame()
    ts_col = "ts" if "ts" in frame.columns else "timestamp" if "timestamp" in frame.columns else None
    if ts_col is None:
        return pd.DataFrame()
    frame["timestamp"] = pd.to_datetime(frame[ts_col], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"])
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    return frame


def _parse_time(raw: str | None) -> pd.Timestamp | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        ts = pd.Timestamp(text)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts


def _frame_to_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        ts = row.get("timestamp")
        if pd.isna(ts):
            continue
        rows.append(
            {
                "timestamp": pd.Timestamp(ts)
                .to_pydatetime()
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "open": float(row.get("open", 0.0)),
                "high": float(row.get("high", 0.0)),
                "low": float(row.get("low", 0.0)),
                "close": float(row.get("close", 0.0)),
                "volume": float(row.get("volume", 0.0)),
            }
        )
    return rows
