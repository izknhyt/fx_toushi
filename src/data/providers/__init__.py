"""Provider adapter scaffolding for data ingestion."""

from __future__ import annotations

from .base import ProviderAdapter
from .csv_loader import CsvLoaderProvider, FakeCsvLoader
from .dukascopy import DukascopyProvider, FakeDukascopyProvider
from .paid_feed_stub import PaidFeedStubProvider
from .yahoo import FakeYahooProvider, YahooProvider

__all__ = [
    "ProviderAdapter",
    "YahooProvider",
    "FakeYahooProvider",
    "DukascopyProvider",
    "FakeDukascopyProvider",
    "CsvLoaderProvider",
    "FakeCsvLoader",
    "PaidFeedStubProvider",
]
