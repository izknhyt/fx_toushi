"""Manual CSV loader provider stub."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from .base import ProviderAdapter
from ..service import MarketFrame, MarketRequest

__all__ = ["CsvLoaderProvider", "FakeCsvLoader"]


@dataclass(slots=True)
class CsvLoaderProvider(ProviderAdapter):  # type: ignore[misc]
    """Adapter that simulates loading bars from a manual CSV source."""

    name: str = "manual_csv"
    root: Path = Path("data/manual_fallback")

    def fetch_bars(self, request: MarketRequest) -> Iterable[MarketFrame]:
        return [
            MarketFrame(
                symbol=symbol,
                timeframe=request.timeframe,
                bars=[{"source": str(self.root), "symbol": symbol}],
            )
            for symbol in request.symbols
        ]


class FakeCsvLoader(CsvLoaderProvider):
    """Configurable CSV loader for tests."""

    def __init__(
        self,
        frames: Sequence[MarketFrame] | None = None,
        *,
        root: Path | None = None,
    ) -> None:
        super().__init__(root=root or Path("/tmp/manual"))
        self._frames = list(frames) if frames is not None else []

    def fetch_bars(self, request: MarketRequest) -> Iterator[MarketFrame]:
        if self._frames:
            return iter(self._frames)
        return iter(super().fetch_bars(request))
