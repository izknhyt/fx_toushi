"""Data ingestion service scaffolding with SLA metrics logging.

The implementation focuses on deterministic scaffolding that downstream CLIs
and tests consume. Real provider integration is left as an extension point,
while the public API and metrics format remain stable per the detailed design
§3.1/§17.6.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence, Mapping

__all__ = [
    "MarketRequest",
    "MarketFrame",
    "ProviderResult",
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
    "load_provider_sla_thresholds",
]

logger = logging.getLogger(__name__)
DEFAULT_METRICS_PATH = Path("metrics") / "data_ingestion_sla.jsonl"


# ---------------------------------------------------------------------------
# Type scaffolds
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class MarketRequest:
    """Request parameters passed to provider adapters."""

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


@dataclass(slots=True)
class ProviderResult:
    """Provider response envelope used for SLA logging."""

    frames: list[MarketFrame]
    p95_ms: float
    p99_ms: float
    rate_limit_ratio: float = 0.0


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
# Helpers
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _log_sla_entry(
    *,
    provider: str,
    timeframe: str,
    symbols: Sequence[str],
    stage: str,
    p95_ms: float,
    p99_ms: float,
    bars: int,
    status: str | None,
    rate_limit_ratio: float = 0.0,
    latency_status: str | None = None,
    metrics_path: Path = DEFAULT_METRICS_PATH,
) -> None:
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    status = status or _compute_latency_status(p95_ms)
    latency_status = latency_status or status
    payload = {
        "ts": _utcnow_iso(),
        "provider": provider,
        "stage": stage,
        "timeframe": timeframe,
        "symbols": list(symbols),
        "fetch_p95_ms": float(p95_ms),
        "fetch_p99_ms": float(p99_ms),
        "bars": bars,
        "429_rate": float(rate_limit_ratio),
        "latency_status": latency_status,
    }
    try:
        with metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
    except OSError:
        pass


def _compute_latency_status(p95_ms: float, *, warn_ms: float = 1_000.0, breach_ms: float = 1_500.0) -> str:
    """Coarse latency health classification."""

    if p95_ms >= breach_ms:
        return "breach"
    if p95_ms >= warn_ms:
        return "watch"
    return "ok"


def load_provider_sla_thresholds(path: Path) -> Mapping[str, tuple[float, float]]:
    """Load provider-specific SLA thresholds from JSON/YAML (JSON subset)."""

    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("data.sla_thresholds.invalid_json", extra={"path": str(path), "error": str(exc)})
        return {}
    if not isinstance(raw, dict):
        return {}
    thresholds: dict[str, tuple[float, float]] = {}
    for provider, obj in raw.items():
        if not isinstance(obj, dict):
            continue
        warn_ms = float(obj.get("warn_ms", 1000.0))
        breach_ms = float(obj.get("breach_ms", 1500.0))
        thresholds[str(provider)] = (warn_ms, breach_ms)
    return thresholds


def _default_provider_fetch(symbols: Sequence[str], timeframe: str) -> ProviderResult:
    frames = [
        MarketFrame(
            symbol=symbol,
            timeframe=timeframe,
            bars=[{"timestamp": _utcnow_iso(), "open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0}],
            quality_flag=0,
        )
        for symbol in symbols
    ]
    return ProviderResult(frames=frames, p95_ms=120.0, p99_ms=150.0, rate_limit_ratio=0.0)


def _invoke_provider(
    *,
    provider: str,
    symbols: Sequence[str],
    timeframe: str,
    handler: Callable[[Sequence[str], str], ProviderResult | list[MarketFrame]] | None,
) -> ProviderResult:
    if handler is None:
        return _default_provider_fetch(symbols, timeframe)
    result = handler(symbols, timeframe)
    if isinstance(result, ProviderResult):
        return result
    if isinstance(result, list):
        return ProviderResult(frames=result, p95_ms=120.0, p99_ms=150.0, rate_limit_ratio=0.0)
    raise ProviderError(f"provider {provider} returned unsupported payload")


# ---------------------------------------------------------------------------
# Public service façade
# ---------------------------------------------------------------------------


def fetch_latest(
    symbols: Sequence[str],
    timeframe: str,
    *,
    provider_priority: Sequence[str] | None = None,
    context: object | None = None,
    retries: int = 2,
    backoff_ms: float = 500.0,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    provider_handlers: dict[str, Callable[[Sequence[str], str], ProviderResult | list[MarketFrame]]] | None = None,
    warn_ms: float = 1_000.0,
    breach_ms: float = 1_500.0,
    provider_sla_thresholds: Mapping[str, tuple[float, float]] | None = None,
) -> list[MarketFrame]:
    """Fetch the most recent bars for the requested symbols and log SLA metrics."""

    _ = context  # reserved for future wiring
    providers = list(provider_priority or ("primary",))
    frames: list[MarketFrame] = []
    handler_map = provider_handlers or {}
    provider_sla_thresholds = provider_sla_thresholds or {}

    for provider in providers:
        retry_budget = retries
        attempt = 0
        warn = provider_sla_thresholds.get(provider, (warn_ms, breach_ms))[0]
        breach = provider_sla_thresholds.get(provider, (warn_ms, breach_ms))[1]
        while retry_budget >= 0:
            try:
                result = _invoke_provider(
                    provider=provider,
                    symbols=symbols,
                    timeframe=timeframe,
                    handler=handler_map.get(provider),
                )
                frames = result.frames
                _log_sla_entry(
                    provider=provider,
                    timeframe=timeframe,
                    symbols=symbols,
                    stage="fetch",
                    p95_ms=result.p95_ms,
                    p99_ms=result.p99_ms,
                    bars=len(frames),
                    status=_compute_latency_status(result.p95_ms, warn_ms=warn, breach_ms=breach),
                    rate_limit_ratio=result.rate_limit_ratio,
                    metrics_path=metrics_path,
                )
                break
            except ProviderError as exc:
                logger.warning("data.fetch_latest.retry", extra={"provider": provider, "error": str(exc), "attempt": attempt})
                _log_sla_entry(
                    provider=provider,
                    timeframe=timeframe,
                    symbols=symbols,
                    stage="fetch",
                    p95_ms=0.0,
                    p99_ms=0.0,
                    bars=0,
                    status="error",
                    rate_limit_ratio=getattr(exc, "rate_limit_ratio", 0.0),
                    metrics_path=metrics_path,
                )
                retry_budget -= 1
                attempt += 1
                if retry_budget < 0:
                    break
                delay_ms = backoff_ms if attempt == 1 else backoff_ms * 2
                logger.info("data.fetch_latest.backoff", extra={"delay_ms": delay_ms, "provider": provider})
                # placeholder: in async/real mode use asyncio.sleep(delay_ms/1000)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("data.fetch_latest.unexpected", extra={"error": str(exc)})
                break
        if frames:
            break
    if not frames:
        _log_sla_entry(
            provider=providers[-1] if providers else "unknown",
            timeframe=timeframe,
            symbols=symbols,
            stage="fetch",
            p95_ms=0.0,
            p99_ms=0.0,
            bars=0,
            status="error",
            rate_limit_ratio=1.0,
            metrics_path=metrics_path,
        )
    return frames


def backfill(
    symbols: Sequence[str],
    timeframe: str,
    start: str,
    end: str,
    *,
    priority: str | None = None,
    context: object | None = None,
    retries: int = 2,
    backoff_ms: float = 500.0,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    warn_ms: float = 1_000.0,
    breach_ms: float = 1_500.0,
    provider_sla_thresholds: Mapping[str, tuple[float, float]] | None = None,
) -> list[MarketFrame]:
    """Backfill the requested window for the given symbols."""

    _ = context
    frames: list[MarketFrame] = []
    for symbol in symbols:
        frames.append(
            MarketFrame(
                symbol=symbol,
                timeframe=timeframe,
                bars=[
                    {"timestamp": start, "open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0},
                    {"timestamp": end, "open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0},
                ],
                quality_flag=0,
            )
        )
    _log_sla_entry(
        provider=str(priority or "backfill"),
        timeframe=timeframe,
        symbols=symbols,
        stage="backfill",
        p95_ms=150.0,
        p99_ms=180.0,
        bars=len(frames) * 2,
        status=_compute_latency_status(
            150.0,
            warn_ms=provider_sla_thresholds.get(priority, (warn_ms, breach_ms))[0] if provider_sla_thresholds else warn_ms,
            breach_ms=provider_sla_thresholds.get(priority, (warn_ms, breach_ms))[1] if provider_sla_thresholds else breach_ms,
        ),
        rate_limit_ratio=0.0,
        metrics_path=metrics_path,
    )
    return frames


def warm_cache(*, context: object | None = None) -> None:
    """Preload provider caches at service startup."""

    _ = context


def spawn_provider_workers(*, context: object | None = None) -> list[object]:
    """Spawn provider fetch/parse workers and return opaque handles."""

    _ = context
    return []


def drain_buffers(*, force: bool = False) -> dict[str, int]:
    """Flush in-flight buffers and return statistics for observability."""

    return {"flushed": 0, "dropped": 0, "forced": int(force)}
