"""Dukascopy provider implementation using tick download + 5m aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import ProviderAdapter
from ..service import MarketFrame, MarketRequest
from tools.dukascopy_fetch import aggregate_to_5m, fetch_hour, parse_bi5

import pandas as pd

__all__ = ["DukascopyProvider", "FakeDukascopyProvider"]


@dataclass(slots=True)
class DukascopyProvider(ProviderAdapter):  # type: ignore[misc]
    """Dukascopy adapter fetching tick data and aggregating to 5m bars."""

    name: str = "dukascopy"

    def fetch_bars(self, request: MarketRequest) -> Iterable[MarketFrame]:
        if not _is_supported_timeframe(request.timeframe):
            return [MarketFrame(symbol=symbol, timeframe=request.timeframe, bars=[]) for symbol in request.symbols]

        start = _parse_time(request.start) or datetime.now(timezone.utc) - timedelta(hours=6)
        end = _parse_time(request.end) or datetime.now(timezone.utc)
        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)

        max_workers = _select_worker_count(start, end, symbols=request.symbols)
        frames: list[MarketFrame] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_dukascopy_bars, symbol, start, end): symbol for symbol in request.symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    bars_df = future.result()
                except Exception:
                    bars_df = pd.DataFrame()
                bars = _bars_from_frame(bars_df)
                frames.append(MarketFrame(symbol=symbol, timeframe=request.timeframe, bars=bars))
        return frames


class FakeDukascopyProvider(DukascopyProvider):
    """Deterministic Dukascopy adapter for tests."""

    def __init__(self, frames: Sequence[MarketFrame] | None = None) -> None:
        super().__init__()
        self._frames = list(frames) if frames is not None else []

    def fetch_bars(self, request: MarketRequest) -> Iterator[MarketFrame]:
        if self._frames:
            return iter(self._frames)
        return iter(super().fetch_bars(request))


def _is_supported_timeframe(timeframe: str) -> bool:
    return timeframe.lower() in {"5m", "5min", "5min"}


def _parse_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _daterange(start: datetime, end: datetime) -> Iterable[datetime]:
    current = start.replace(minute=0, second=0, microsecond=0)
    while current <= end:
        yield current
        current += timedelta(hours=1)


def _fetch_dukascopy_bars(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    cache_dir = Path("data/cache/dukascopy")
    for when in _daterange(start, end):
        raw = fetch_hour(symbol, when, cache_dir=cache_dir)
        if not raw:
            continue
        ticks = parse_bi5(raw, when)
        if ticks.empty:
            continue
        bars = aggregate_to_5m(ticks)
        if bars.empty:
            continue
        frames.append(bars)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _bars_from_frame(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    if "timestamp" not in frame.columns:
        return []
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    bars: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        ts = row.get("timestamp")
        if pd.isna(ts):
            continue
        bars.append(
            {
                "timestamp": ts.to_pydatetime().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "open": float(row.get("open", 0.0)),
                "high": float(row.get("high", 0.0)),
                "low": float(row.get("low", 0.0)),
                "close": float(row.get("close", 0.0)),
                "volume": float(row.get("volume", 0.0)),
            }
        )
    return bars


def _select_worker_count(start: datetime, end: datetime, *, symbols: Sequence[str]) -> int:
    env_value = os.getenv("DUKASCOPY_MAX_WORKERS")
    if env_value:
        try:
            parsed = int(env_value)
            return max(1, parsed)
        except ValueError:
            pass
    window_hours = max((end - start).total_seconds() / 3600, 0.0)
    if window_hours >= 6:
        return min(6, max(1, len(symbols)))
    if window_hours >= 1:
        return min(4, max(1, len(symbols)))
    return min(2, max(1, len(symbols)))
