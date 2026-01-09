"""Shared provider protocol definitions."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from ..service import MarketFrame, MarketRequest

__all__ = ["ProviderAdapter"]


@runtime_checkable
class ProviderAdapter(Protocol):
    """Protocol that concrete provider adapters must satisfy."""

    name: str

    def fetch_bars(self, request: MarketRequest) -> Iterable[MarketFrame]:
        """Return an iterable of market frames for the supplied request."""
