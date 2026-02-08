"""Twelve Data provider adapter."""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

from ..service import MarketFrame, MarketRequest
from .base import ProviderAdapter

__all__ = ["TwelveDataProvider", "FakeTwelveDataProvider"]

_API_URL = "https://api.twelvedata.com/time_series"


@dataclass(slots=True)
class TwelveDataProvider(ProviderAdapter):  # type: ignore[misc]
    """Twelve Data provider for recent candles."""

    name: str = "twelvedata"
    timeout_sec: float | None = 15.0
    api_key: str | None = None
    drop_last_bar: bool = True

    def fetch_bars(self, request: MarketRequest) -> Iterable[MarketFrame]:
        api_key = self.api_key or os.getenv("TWELVEDATA_API_KEY")
        if not api_key:
            raise RuntimeError("TWELVEDATA_API_KEY is not set")

        start = _parse_time(request.start)
        end = _parse_time(request.end) or _utcnow()
        interval = _normalize_interval(request.timeframe)
        outputsize = _estimate_outputsize(start, end, interval)

        frames: list[MarketFrame] = []
        for symbol in request.symbols:
            bars = _fetch_symbol_bars(
                symbol=symbol,
                interval=interval,
                outputsize=outputsize,
                api_key=api_key,
                timeout_sec=self.timeout_sec,
            )
            if interval == "5min" and self.drop_last_bar:
                bars = _filter_confirmed_bars(bars, now=end)
            frames.append(MarketFrame(symbol=symbol, timeframe=request.timeframe, bars=bars))
        return frames


class FakeTwelveDataProvider(TwelveDataProvider):
    """Deterministic provider for tests."""

    def __init__(self, frames: Sequence[MarketFrame] | None = None) -> None:
        super().__init__()
        self._frames = list(frames) if frames is not None else []

    def fetch_bars(self, request: MarketRequest) -> Iterator[MarketFrame]:
        if self._frames:
            return iter(self._frames)
        return iter(super().fetch_bars(request))


def _fetch_symbol_bars(
    *,
    symbol: str,
    interval: str,
    outputsize: int,
    api_key: str,
    timeout_sec: float | None,
) -> list[dict[str, object]]:
    params = {
        "symbol": _normalize_symbol(symbol),
        "interval": interval,
        "outputsize": outputsize,
        "apikey": api_key,
    }
    response = requests.get(_API_URL, params=params, timeout=timeout_sec or 15.0)
    data = response.json() if response.content else {}
    if response.status_code != 200 or data.get("status") == "error":
        return []
    values = data.get("values") or []
    if not isinstance(values, list):
        return []

    bars: list[dict[str, object]] = []
    for row in reversed(values):
        ts = row.get("datetime")
        if not ts:
            continue
        parsed = _parse_twelvedata_time(ts)
        if parsed is None:
            continue
        bars.append(
            {
                "ts": parsed.isoformat().replace("+00:00", "Z"),
                "open": float(row.get("open", 0.0)),
                "high": float(row.get("high", 0.0)),
                "low": float(row.get("low", 0.0)),
                "close": float(row.get("close", 0.0)),
                "volume": float(row.get("volume", 0.0)),
            }
        )
    return bars


def _filter_confirmed_bars(
    bars: list[dict[str, object]],
    *,
    now: datetime,
) -> list[dict[str, object]]:
    if not bars:
        return bars
    anchor = _floor_time(now, minutes=5)
    confirmed: list[dict[str, object]] = []
    for bar in bars:
        ts = bar.get("ts")
        parsed = _parse_time(ts)
        if parsed is None:
            continue
        if parsed >= anchor:
            continue
        confirmed.append(bar)
    return confirmed


def _floor_time(value: datetime, *, minutes: int) -> datetime:
    value = value.astimezone(timezone.utc)
    floored_minute = value.minute - (value.minute % minutes)
    return value.replace(minute=floored_minute, second=0, microsecond=0)


def _estimate_outputsize(start: datetime | None, end: datetime, interval: str) -> int:
    if start is None:
        return 100
    delta = max(end - start, timedelta(minutes=1))
    minutes = int(delta.total_seconds() // 60)
    step = _interval_minutes(interval)
    if step <= 0:
        step = 5
    count = minutes // step + 3
    return min(max(count, 10), 5000)


def _interval_minutes(interval: str) -> int:
    if interval == "1min":
        return 1
    if interval == "5min":
        return 5
    if interval == "15min":
        return 15
    if interval == "1h":
        return 60
    return 5


def _normalize_interval(timeframe: str) -> str:
    lowered = timeframe.lower()
    if lowered in {"1m", "1min"}:
        return "1min"
    if lowered in {"5m", "5min"}:
        return "5min"
    if lowered in {"15m", "15min"}:
        return "15min"
    if lowered in {"1h", "60m", "1hour"}:
        return "1h"
    return "5min"


def _normalize_symbol(symbol: str) -> str:
    if "/" in symbol:
        return symbol.upper()
    text = symbol.upper()
    if len(text) == 6 and text.isalpha():
        return f"{text[:3]}/{text[3:]}"
    return text


def _parse_twelvedata_time(raw: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_time(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    try:
        text = raw
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
