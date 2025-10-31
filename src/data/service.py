"""Data ingestion service scaffolding.

This module provides type hints and exception contracts for the
``DataIngestionService`` façade described in detailed_design_fx_signal_tool_v1.md
§3.1.  The implementations are intentionally left as placeholders so that
future Codex deliverables can extend them without breaking import contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

__all__ = [
    "MarketRequest",
    "MarketFrame",
    "ProviderError",
    "DataSourceDown",
    "DataQualityError",
    "BackfillRangeError",
    "BackfillFailed",
    "CacheWarmupError",
    "WorkerSpawnError",
    "BufferDrainError",
    "fetch_latest",
    "backfill",
    "warm_cache",
    "spawn_provider_workers",
    "drain_buffers",
]


# ---------------------------------------------------------------------------
# Type scaffolds
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class MarketRequest:
    """Request parameters passed to provider adapters.

    Attributes mirror the design contract for ``ProviderFetchWorker`` and are
    sufficient for tests to construct deterministic fake responses.
    """

    symbols: Sequence[str]
    timeframe: str
    start: str | None = None
    end: str | None = None
    provider_priority: Sequence[str] | None = None


@dataclass(slots=True)
class MarketFrame:
    """Placeholder market frame returned by the ingestion service."""

    symbol: str
    timeframe: str
    bars: list[dict[str, object]]
    quality_flag: int = 0


# ---------------------------------------------------------------------------
# Exception hierarchy (see detailed design §3.1)
# ---------------------------------------------------------------------------


class DataIngestionError(RuntimeError):
    """Base class for ingestion related failures."""


class ProviderError(DataIngestionError):
    """Raised when the upstream data provider fails to serve a request."""


class DataSourceDown(ProviderError):
    """Raised after all fallback providers failed to supply bars."""


class DataQualityError(DataIngestionError):
    """Raised when ``DataQualityGuard`` rejects a frame."""


class BackfillRangeError(DataIngestionError):
    """Raised when a requested backfill window is invalid."""


class BackfillFailed(DataIngestionError):
    """Raised when a backfill job exhausts its retries without success."""


class CacheWarmupError(DataIngestionError):
    """Raised when cache preloading fails during startup."""


class WorkerSpawnError(DataIngestionError):
    """Raised when provider workers cannot be instantiated."""


class BufferDrainError(DataIngestionError):
    """Raised when shutdown cannot safely flush in-flight buffers."""


# ---------------------------------------------------------------------------
# Public service façade (placeholders)
# ---------------------------------------------------------------------------


def fetch_latest(
    symbols: Sequence[str],
    timeframe: str,
    *,
    provider_priority: Sequence[str] | None = None,
    context: object | None = None,
) -> list[MarketFrame]:
    """Fetch the most recent bars for the requested symbols.

    The concrete implementation is expected to orchestrate provider selection,
    enqueue fetch work, and emit latency metrics.  This placeholder simply
    advertises the call signature required by §3.1.
    """

    raise NotImplementedError("fetch_latest is scaffolded; provide an implementation")


def backfill(
    symbols: Sequence[str],
    timeframe: str,
    start: str,
    end: str,
    *,
    priority: str | None = None,
    context: object | None = None,
) -> list[MarketFrame]:
    """Backfill the requested window for the given symbols."""

    raise NotImplementedError("backfill is scaffolded; provide an implementation")


def warm_cache(*, context: object | None = None) -> None:
    """Preload provider caches at service startup."""

    raise NotImplementedError("warm_cache is scaffolded; provide an implementation")


def spawn_provider_workers(*, context: object | None = None) -> list[object]:
    """Spawn provider fetch/parse workers and return opaque handles."""

    raise NotImplementedError(
        "spawn_provider_workers is scaffolded; provide an implementation"
    )


def drain_buffers(*, force: bool = False) -> dict[str, int]:
    """Flush in-flight buffers and return statistics for observability."""

    raise NotImplementedError("drain_buffers is scaffolded; provide an implementation")
