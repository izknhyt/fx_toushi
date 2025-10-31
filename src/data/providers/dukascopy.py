"""Stub Dukascopy provider implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

from .base import ProviderAdapter
from ..service import MarketFrame, MarketRequest

__all__ = ["DukascopyProvider", "FakeDukascopyProvider"]


@dataclass(slots=True)
class DukascopyProvider(ProviderAdapter):  # type: ignore[misc]
    """Minimal Dukascopy adapter returning placeholder frames."""

    name: str = "dukascopy"

    def fetch_bars(self, request: MarketRequest) -> Iterable[MarketFrame]:
        return [
            MarketFrame(
                symbol=symbol,
                timeframe=request.timeframe,
                bars=[{"ts": request.start, "close": 0.0}] if request.start else [],
            )
            for symbol in request.symbols
        ]


class FakeDukascopyProvider(DukascopyProvider):
    """Deterministic Dukascopy adapter for tests."""

    def __init__(self, frames: Sequence[MarketFrame] | None = None) -> None:
        super().__init__()
        self._frames = list(frames) if frames is not None else []

    def fetch_bars(self, request: MarketRequest) -> Iterator[MarketFrame]:
        if self._frames:
            return iter(self._frames)
        return iter(super().fetch_bars(request))
