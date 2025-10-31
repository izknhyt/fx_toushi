"""Stub Yahoo Finance provider implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

from .base import ProviderAdapter
from ..service import MarketFrame, MarketRequest

__all__ = ["YahooProvider", "FakeYahooProvider"]


@dataclass(slots=True)
class YahooProvider(ProviderAdapter):  # type: ignore[misc]
    """Minimal Yahoo Finance provider returning placeholder frames."""

    name: str = "yahoo"

    def fetch_bars(self, request: MarketRequest) -> Iterable[MarketFrame]:
        """Return empty frames for each symbol to satisfy the protocol."""

        return [
            MarketFrame(symbol=symbol, timeframe=request.timeframe, bars=[])
            for symbol in request.symbols
        ]


class FakeYahooProvider(YahooProvider):
    """Deterministic provider for tests."""

    def __init__(self, frames: Sequence[MarketFrame] | None = None) -> None:
        super().__init__()
        self._frames = list(frames) if frames is not None else []

    def fetch_bars(self, request: MarketRequest) -> Iterator[MarketFrame]:
        if self._frames:
            return iter(self._frames)
        return iter(super().fetch_bars(request))
