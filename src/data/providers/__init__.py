"""Provider adapter scaffolding for data ingestion."""

from __future__ import annotations

from .base import ProviderAdapter
from .csv_loader import CsvLoaderProvider, FakeCsvLoader
from .dukascopy import DukascopyProvider, FakeDukascopyProvider
from .paid_feed import PaidFeedProvider
from .paid_feed_stub import PaidFeedStubProvider
from .twelvedata import FakeTwelveDataProvider, TwelveDataProvider
from .yahoo import FakeYahooProvider, YahooProvider

__all__ = [
    "ProviderAdapter",
    "YahooProvider",
    "FakeYahooProvider",
    "DukascopyProvider",
    "FakeDukascopyProvider",
    "TwelveDataProvider",
    "FakeTwelveDataProvider",
    "CsvLoaderProvider",
    "FakeCsvLoader",
    "PaidFeedProvider",
    "PaidFeedStubProvider",
]
