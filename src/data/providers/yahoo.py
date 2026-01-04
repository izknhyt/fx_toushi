"""Stub Yahoo Finance provider implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Iterator, Sequence

from .base import ProviderAdapter
from ..service import MarketFrame, MarketRequest

__all__ = ["YahooProvider", "FakeYahooProvider"]


@dataclass(slots=True)
class YahooProvider(ProviderAdapter):  # type: ignore[misc]
    """Minimal Yahoo Finance provider returning placeholder frames."""

    name: str = "yahoo"

    def fetch_bars(self, request: MarketRequest) -> Iterable[MarketFrame]:
        """Return recent bars using yfinance when available."""

        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("yfinance is not installed") from exc

        start = _parse_time(request.start) or datetime.utcnow() - timedelta(hours=6)
        end = _parse_time(request.end) or datetime.utcnow()
        interval = _normalize_interval(request.timeframe)
        frames: list[MarketFrame] = []
        for symbol in request.symbols:
            ticker = _normalize_symbol(symbol)
            df = yf.download(
                tickers=ticker,
                start=start,
                end=end + timedelta(minutes=1),
                interval=interval,
                progress=False,
                auto_adjust=False,
                prepost=False,
                threads=False,
            )
            if df is None or df.empty:
                frames.append(MarketFrame(symbol=symbol, timeframe=request.timeframe, bars=[]))
                continue
            df = df.reset_index()
            df.columns = [str(col).lower().replace(" ", "_") for col in df.columns]
            bars = []
            for _, row in df.iterrows():
                ts = row.get("datetime") or row.get("date")
                if ts is None:
                    continue
                bars.append(
                    {
                        "ts": ts.isoformat(),
                        "open": float(row.get("open", 0.0)),
                        "high": float(row.get("high", 0.0)),
                        "low": float(row.get("low", 0.0)),
                        "close": float(row.get("close", 0.0)),
                        "volume": float(row.get("volume", 0.0)),
                    }
                )
            frames.append(MarketFrame(symbol=symbol, timeframe=request.timeframe, bars=bars))
        return frames


class FakeYahooProvider(YahooProvider):
    """Deterministic provider for tests."""

    def __init__(self, frames: Sequence[MarketFrame] | None = None) -> None:
        super().__init__()
        self._frames = list(frames) if frames is not None else []

    def fetch_bars(self, request: MarketRequest) -> Iterator[MarketFrame]:
        if self._frames:
            return iter(self._frames)
        return iter(super().fetch_bars(request))


def _normalize_symbol(symbol: str) -> str:
    if "=" in symbol:
        return symbol
    if len(symbol) == 6:
        return f"{symbol.upper()}=X"
    return symbol


def _normalize_interval(timeframe: str) -> str:
    lowered = timeframe.lower()
    if lowered in {"5m", "5min", "5min"}:
        return "5m"
    if lowered in {"1m", "1min"}:
        return "1m"
    if lowered in {"1h", "60m"}:
        return "60m"
    return "5m"


def _parse_time(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    try:
        text = raw
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None
