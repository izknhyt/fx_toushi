"""Data ingestion service scaffolding with SLA metrics logging.

The implementation focuses on deterministic scaffolding that downstream CLIs
and tests consume. Provider handlers remain optional extension points; paid
feed adapters and profile-based retry/backoff tuning are wired while the
public API and metrics format remain stable per the detailed design §3.1/§17.6.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from src.data.rate_limit_guard import RateLimitGuard, StageDecision
from src.data.fallback import DEFAULT_FALLBACK_LOG, FallbackRetryTask, record_fallback_event

if TYPE_CHECKING:
    from src.core.health import HealthMonitor
    from src.data.quality import DataQualityGuard


@dataclass(slots=True)
class WorkerPlan:
    provider: str
    stage: str
    poll_interval_sec: float
    max_workers: int


@dataclass(slots=True)
class ProviderProfile:
    timeout_sec: float | None = None
    retry_max_attempts: int | None = None
    retry_backoff_sec: float | None = None


__all__ = [
    "MarketRequest",
    "MarketFrame",
    "BackfillResult",
    "ProviderResult",
    "ProviderError",
    "DataSourceDownError",
    "DataQualityError",
    "BackfillRangeError",
    "BackfillFailedError",
    "CacheWarmupError",
    "WorkerSpawnError",
    "BufferDrainError",
    "BufferCoordinator",
    "fetch_latest",
    "backfill",
    "warm_cache",
    "spawn_provider_workers",
    "drain_buffers",
    "load_provider_sla_thresholds",
    "load_provider_priority",
    "load_ingestion_priorities",
    "resolve_provider_priority",
    "order_symbols_by_priority",
    "build_provider_handlers",
    "IngestionMetricsCollector",
    "WorkerPlan",
    "log_processing_delay",
    "run_worker_plan",
    "run_fetch_workers",
    "ProviderProfile",
    "load_provider_profiles",
]

logger = logging.getLogger(__name__)
DEFAULT_METRICS_PATH = Path("metrics") / "data_ingestion_sla.jsonl"
DEFAULT_PROVIDER_PRIORITY_PATH = Path("config") / "provider_priority.yaml"
DEFAULT_INGESTION_PRIORITY_PATH = Path("config") / "ingestion" / "priorities.yaml"
DEFAULT_PROVIDER_PROFILE_PATH = Path("config") / "provider_profiles" / "local.yaml"
DEFAULT_BAR_READY_QUEUE = Path("data") / "queues" / "bar_ready.jsonl"
DEFAULT_OPS_WORKLOG_PATH = Path("ops_worklog.jsonl")
DEFAULT_MAX_WORKERS_NORMAL = 4
DEFAULT_MAX_WORKERS_CATCH_UP = 6


def load_provider_priority(
    path: Path = DEFAULT_PROVIDER_PRIORITY_PATH,
) -> Mapping[str, Any]:
    """Load provider priority configuration from YAML."""

    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return {}
    return payload


def load_provider_profiles(
    path: Path = DEFAULT_PROVIDER_PROFILE_PATH,
) -> Mapping[str, Any]:
    """Load provider profile overrides for retry/backoff/timeout."""

    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _merge_profile(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def _coerce_int(raw: object) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _coerce_float(raw: object) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_provider_profile(raw: Mapping[str, Any]) -> ProviderProfile:
    retry = raw.get("retry") if isinstance(raw.get("retry"), Mapping) else {}
    max_attempts = _coerce_int(retry.get("max_attempts"))
    backoff_sec = _coerce_float(retry.get("backoff_sec"))
    timeout_sec = _coerce_float(raw.get("timeout_sec"))
    return ProviderProfile(
        timeout_sec=timeout_sec,
        retry_max_attempts=max_attempts if max_attempts and max_attempts > 0 else None,
        retry_backoff_sec=backoff_sec if backoff_sec and backoff_sec >= 0 else None,
    )


def _resolve_provider_profile(
    provider: str, profiles: Mapping[str, Any] | None
) -> ProviderProfile:
    if not profiles:
        return ProviderProfile()
    defaults = profiles.get("defaults") if isinstance(profiles.get("defaults"), Mapping) else {}
    providers = profiles.get("providers") if isinstance(profiles.get("providers"), Mapping) else {}
    merged = _merge_profile(defaults, providers.get(provider, {}) if isinstance(providers, Mapping) else {})
    if not isinstance(merged, Mapping):
        return ProviderProfile()
    return _parse_provider_profile(merged)


def _resolve_retry_settings(
    provider: str,
    profiles: Mapping[str, Any] | None,
    *,
    default_retries: int,
    default_backoff_ms: float,
) -> tuple[int, float]:
    profile = _resolve_provider_profile(provider, profiles)
    retries = default_retries
    if profile.retry_max_attempts is not None:
        retries = max(profile.retry_max_attempts - 1, 0)
    backoff_ms = default_backoff_ms
    if profile.retry_backoff_sec is not None:
        backoff_ms = max(profile.retry_backoff_sec * 1000.0, 0.0)
    return retries, backoff_ms


def resolve_provider_priority(
    symbols: Sequence[str],
    *,
    provider_priority: Sequence[str] | None = None,
    config_path: Path = DEFAULT_PROVIDER_PRIORITY_PATH,
) -> list[str]:
    """Resolve provider priority list using config defaults and per-symbol overrides."""

    if provider_priority:
        return list(provider_priority)
    config = load_provider_priority(config_path)
    per_symbol = config.get("per_symbol") or {}
    default_order = config.get("default_order") or []
    if symbols:
        primary_symbol = str(symbols[0])
        override = per_symbol.get(primary_symbol) or per_symbol.get(primary_symbol.upper())
        if override:
            return list(override)
    if default_order:
        return list(default_order)
    return ["primary"]


def _truthy_env(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _read_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def load_ingestion_priorities(
    path: Path = DEFAULT_INGESTION_PRIORITY_PATH,
) -> Mapping[str, Mapping[str, float]]:
    """Load ingestion priority weights for symbols/timeframes."""

    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return {}
    symbol_weight = payload.get("symbol_weight") or {}
    timeframe_weight = payload.get("timeframe_weight") or {}
    return {"symbol_weight": symbol_weight, "timeframe_weight": timeframe_weight}


def _read_feature_flag(
    flag: str,
    *,
    profile: str | None = None,
    path: Path = Path("config/feature_flags.yaml"),
) -> bool:
    profile = profile or os.getenv("TRADECTL_PROFILE")
    if not profile or not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") or {}
    profile_defaults = defaults.get(profile)
    if not isinstance(profile_defaults, dict):
        return False
    return bool(profile_defaults.get(flag, False))


def order_symbols_by_priority(
    symbols: Sequence[str],
    *,
    timeframe: str,
    priorities: Mapping[str, Mapping[str, float]] | None = None,
) -> list[str]:
    """Sort symbols by configured weights to stabilize ingestion ordering."""

    if not priorities:
        return list(symbols)
    symbol_weight = priorities.get("symbol_weight", {})
    timeframe_weight = priorities.get("timeframe_weight", {})
    tf_weight = float(timeframe_weight.get(timeframe, 1.0))

    def _score(symbol: str) -> float:
        return float(symbol_weight.get(symbol, 1.0)) * tf_weight

    return sorted(symbols, key=_score, reverse=True)


def build_provider_handlers(
    *,
    timeframe: str,
    start: str | None = None,
    end: str | None = None,
    provider_profiles: Mapping[str, Any] | None = None,
) -> dict[str, Callable[[Sequence[str], str], ProviderResult | list[MarketFrame]]]:
    """Build default provider handlers for known adapters."""

    handlers: dict[str, Callable[[Sequence[str], str], ProviderResult | list[MarketFrame]]] = {}
    try:
        from src.data.providers.yahoo import YahooProvider

        profile = _resolve_provider_profile("yfinance", provider_profiles)
        yahoo = YahooProvider(timeout_sec=profile.timeout_sec)

        def _yahoo_handler(symbols: Sequence[str], timeframe: str) -> list[MarketFrame]:
            request = MarketRequest(symbols=symbols, timeframe=timeframe, start=start, end=end)
            return list(yahoo.fetch_bars(request))

        handlers["yfinance"] = _yahoo_handler
    except Exception:
        pass
    try:
        from src.data.providers.dukascopy import DukascopyProvider

        profile = _resolve_provider_profile("dukascopy", provider_profiles)
        duka = DukascopyProvider(
            timeout_sec=profile.timeout_sec,
            retries=profile.retry_max_attempts,
            backoff_sec=profile.retry_backoff_sec,
        )

        def _duka_handler(symbols: Sequence[str], timeframe: str) -> list[MarketFrame]:
            request = MarketRequest(symbols=symbols, timeframe=timeframe, start=start, end=end)
            return list(duka.fetch_bars(request))

        handlers["dukascopy"] = _duka_handler
    except Exception:
        pass
    try:
        from src.data.providers.local_parquet import parquet_provider

        def _local_handler(symbols: Sequence[str], timeframe: str) -> ProviderResult:
            return parquet_provider(symbols=symbols, timeframe=timeframe)

        handlers["local_parquet"] = _local_handler
    except Exception:
        pass
    try:
        from src.data.providers.csv_loader import CsvLoaderProvider

        manual = CsvLoaderProvider()

        def _manual_handler(symbols: Sequence[str], timeframe: str) -> list[MarketFrame]:
            request = MarketRequest(symbols=symbols, timeframe=timeframe, start=start, end=end)
            return list(manual.fetch_bars(request))

        handlers["manual_csv"] = _manual_handler
    except Exception:
        pass
    if _read_feature_flag("data.paid_feed"):
        try:
            provider_name = os.getenv("TRADECTL_PAID_FEED_PROVIDER") or "paid_feed"
            if provider_name == "paid_feed_stub":
                from src.data.providers.paid_feed_stub import PaidFeedStubProvider

                paid_feed = PaidFeedStubProvider()
                handler_name = "paid_feed_stub"
            else:
                from src.data.providers.paid_feed import PaidFeedProvider

                profile = _resolve_provider_profile(provider_name, provider_profiles)
                paid_feed = PaidFeedProvider(timeout_sec=profile.timeout_sec)
                handler_name = provider_name

            def _paid_feed_handler(symbols: Sequence[str], timeframe: str) -> list[MarketFrame]:
                request = MarketRequest(symbols=symbols, timeframe=timeframe, start=start, end=end)
                return list(paid_feed.fetch_bars(request))

            handlers[handler_name] = _paid_feed_handler
        except Exception:
            pass
    return handlers


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
class BackfillResult:
    """Backfill result envelope used by resync orchestration."""

    frames: list[MarketFrame]
    provider_used: str | None
    retry_count: int
    status: str


@dataclass(slots=True)
class ProviderResult:
    """Provider response envelope used for SLA logging."""

    frames: list[MarketFrame]
    p95_ms: float
    p99_ms: float
    rate_limit_ratio: float = 0.0


@dataclass(slots=True)
class BufferItem:
    """Queued provider payload awaiting processing."""

    provider: str
    symbols: list[str]
    timeframe: str
    request_ts: datetime
    enqueue_ts: datetime
    frames: list[MarketFrame]


class BufferCoordinator:
    """Minimal queue wrapper to separate fetch and processing timing."""

    def __init__(
        self,
        *,
        maxsize: int = 256,
        fetch_timeout_sec: float = 18.0,
        processing_timeout_sec: float = 12.0,
    ) -> None:
        self._queue: deque[BufferItem] = deque()
        self._maxsize = maxsize
        self.fetch_timeout_sec = fetch_timeout_sec
        self.processing_timeout_sec = processing_timeout_sec
        self._dropped = 0

    def enqueue(
        self,
        *,
        provider: str,
        symbols: Sequence[str],
        timeframe: str,
        request_ts: datetime,
        frames: list[MarketFrame],
    ) -> BufferItem:
        if len(self._queue) >= self._maxsize:
            self._queue.popleft()
            self._dropped += 1
        item = BufferItem(
            provider=provider,
            symbols=list(symbols),
            timeframe=timeframe,
            request_ts=request_ts,
            enqueue_ts=datetime.now(timezone.utc),
            frames=frames,
        )
        self._queue.append(item)
        return item

    def pop(self) -> BufferItem | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def drain(self, *, force: bool = False) -> dict[str, int]:
        flushed = len(self._queue)
        self._queue.clear()
        return {"flushed": flushed, "dropped": self._dropped, "forced": int(force)}

    def __len__(self) -> int:
        return len(self._queue)


DEFAULT_BUFFER_COORDINATOR = BufferCoordinator()


# ---------------------------------------------------------------------------
# Metrics collector
# ---------------------------------------------------------------------------


class IngestionMetricsCollector:
    """In-memory latency collector with optional raw logging and snapshots."""

    def __init__(
        self,
        *,
        window_size: int = 200,
        warn_ms: float = 1_000.0,
        breach_ms: float = 1_500.0,
        raw_log_dir: Path | None = None,
        max_raw_lines: int = 100_000,
    ) -> None:
        self.window_size = window_size
        self.warn_ms = warn_ms
        self.breach_ms = breach_ms
        self.raw_log_dir = Path(raw_log_dir) if raw_log_dir else None
        self.max_raw_lines = max_raw_lines
        self._latencies: deque[float] = deque(maxlen=window_size)
        self._failures: int = 0
        self._last_bars: int = 0
        self._last_provider: str | None = None
        self._last_symbols: list[str] = []
        self._last_stage: str = "fetch"
        self._last_timeframe: str = "unknown"

    def observe(
        self,
        *,
        provider: str,
        symbols: Iterable[str],
        timeframe: str,
        latency_ms: float,
        bars: int,
        stage: str = "fetch",
        rate_limit_ratio: float = 0.0,
        success: bool = True,
    ) -> None:
        """Record a single attempt latency and optionally write raw log."""

        now = _utcnow_iso()
        self._last_provider = provider
        self._last_symbols = list(symbols)
        self._last_stage = stage
        self._last_timeframe = timeframe
        self._last_bars = bars
        if success:
            self._latencies.append(float(latency_ms))
        else:
            self._failures += 1
        record = {
            "ts": now,
            "provider": provider,
            "stage": stage,
            "timeframe": timeframe,
            "symbols": list(symbols),
            "latency_ms": float(latency_ms),
            "bars": bars,
            "rate_limit_ratio": float(rate_limit_ratio),
            "success": bool(success),
        }
        self._write_raw_record(record)

    def snapshot(self) -> Mapping[str, Any]:
        """Return p95/p99 and retry_count based on observed latencies."""

        p95 = _percentile(self._latencies, 95)
        p99 = _percentile(self._latencies, 99)
        status = "unknown"
        if p95 is not None:
            status = _compute_latency_status(p95, warn_ms=self.warn_ms, breach_ms=self.breach_ms)
        return {
            "fetch_p95_ms": p95,
            "fetch_p99_ms": p99,
            "retry_count": self._failures,
            "latency_status": status,
            "bars": self._last_bars,
            "provider": self._last_provider,
            "symbols": list(self._last_symbols),
            "stage": self._last_stage,
            "timeframe": self._last_timeframe,
        }

    def write_snapshot(self, *, metrics_path: Path = DEFAULT_METRICS_PATH) -> None:
        """Append a snapshot to the SLA metrics log if observations exist."""

        snap = self.snapshot()
        if snap.get("fetch_p95_ms") is None:
            return
        _log_sla_entry(
            provider=snap.get("provider") or "resync",
            timeframe=snap.get("timeframe") or "unknown",
            symbols=snap.get("symbols") or [],
            stage=snap.get("stage") or "fetch",
            p95_ms=float(snap["fetch_p95_ms"]),
            p99_ms=float(snap.get("fetch_p99_ms") or snap["fetch_p95_ms"]),
            bars=int(snap.get("bars") or 0),
            status=snap.get("latency_status") or "unknown",
            rate_limit_ratio=0.0,
            metrics_path=metrics_path,
            latency_status=snap.get("latency_status"),
        )

    def _write_raw_record(self, record: Mapping[str, Any]) -> None:
        if not self.raw_log_dir:
            return
        ts = str(record.get("ts") or _utcnow_iso())
        date_part = ts.split("T")[0]
        base = self.raw_log_dir / f"data_ingestion_raw_{date_part}.jsonl"
        path = self._ensure_capacity(base)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False))
                handle.write("\n")
        except OSError:
            return

    def _ensure_capacity(self, path: Path) -> Path:
        """Rotate raw log if max_raw_lines exceeded."""

        if self.max_raw_lines <= 0:
            return path
        if path.exists():
            try:
                line_count = sum(1 for _ in path.open("r", encoding="utf-8"))
            except OSError:
                return path
            if line_count < self.max_raw_lines:
                return path
        suffix = 1
        while True:
            candidate = path.with_name(f"{path.stem}_part{suffix}{path.suffix}")
            if not candidate.exists():
                return candidate
            try:
                line_count = sum(1 for _ in candidate.open("r", encoding="utf-8"))
            except OSError:
                return candidate
            if line_count < self.max_raw_lines:
                return candidate
            suffix += 1


# ---------------------------------------------------------------------------
# Exception hierarchy (see detailed design §3.1)
# ---------------------------------------------------------------------------


class DataIngestionError(RuntimeError):
    """Base class for ingestion related failures."""


class ProviderError(DataIngestionError):
    """Raised when the upstream data provider fails to serve a request."""


class DataSourceDownError(ProviderError):
    """Raised after all fallback providers failed to supply bars."""


class DataQualityError(DataIngestionError):
    """Raised when ``DataQualityGuard`` rejects a frame."""

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class BackfillRangeError(DataIngestionError):
    """Raised when a requested backfill window is invalid."""


class BackfillFailedError(DataIngestionError):
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
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    """Compute a percentile with linear interpolation; return None if empty."""

    data = sorted(float(v) for v in values)
    if not data:
        return None
    if len(data) == 1:
        return data[0]
    k = (len(data) - 1) * (percentile / 100.0)
    f = int(k)
    c = min(f + 1, len(data) - 1)
    if f == c:
        return data[f]
    return data[f] * (c - k) + data[c] * (k - f)


def _parse_bar_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _extract_last_bar_timestamp(frames: Sequence[MarketFrame]) -> datetime | None:
    latest: datetime | None = None
    for frame in frames:
        if not frame.bars:
            continue
        candidate = frame.bars[-1].get("timestamp") or frame.bars[-1].get("ts")
        parsed = _parse_bar_timestamp(candidate)
        if parsed is None:
            continue
        if latest is None or parsed > latest:
            latest = parsed
    return latest


def _compute_bar_gap_minutes(anchor: datetime, last_bar: datetime | None) -> int | None:
    if last_bar is None:
        return None
    gap = int((anchor - last_bar).total_seconds() // 60)
    return max(gap, 0)


def _chunk_backfill_ranges(
    start: datetime, end: datetime, *, chunk_hours: int
) -> Iterable[tuple[datetime, datetime]]:
    if chunk_hours <= 0:
        yield start, end
        return
    cursor = start
    step = chunk_hours * 3600
    while cursor < end:
        chunk_end = min(end, cursor + timedelta(seconds=step))
        if chunk_end <= cursor:
            break
        yield cursor, chunk_end
        cursor = chunk_end


def _maybe_raise_data_latency(
    monitor: HealthMonitor | None,
    *,
    delay_sec: float | None,
    bar_gap_minutes: int | None,
    provider: str,
    symbols: Sequence[str],
    fetch_delay_warn_sec: float,
    bar_gap_warn_minutes: int,
) -> None:
    if monitor is None:
        return
    reasons: list[str] = []
    if delay_sec is not None and delay_sec > fetch_delay_warn_sec:
        reasons.append(f"fetch_delay_sec={delay_sec:.2f}")
    if bar_gap_minutes is not None and bar_gap_minutes > bar_gap_warn_minutes:
        reasons.append(f"bar_gap_minutes={bar_gap_minutes}")
    if not reasons:
        return
    detail = ";".join(reasons)
    monitor.raise_condition(
        "degraded",
        "data_latency_fetch",
        detail=f"{detail};provider={provider};symbols={','.join(symbols)}",
        recommended_action="runbook:RUN-DATA-05#enter_guarded",
    )


def _maybe_raise_processing_latency(
    monitor: HealthMonitor | None,
    *,
    delay_sec: float | None,
    provider: str,
    symbols: Sequence[str],
    processing_delay_warn_sec: float,
) -> None:
    if monitor is None or delay_sec is None:
        return
    if delay_sec <= processing_delay_warn_sec:
        return
    monitor.raise_condition(
        "degraded",
        "data_latency_processing",
        detail=(
            f"processing_delay_sec={delay_sec:.2f};provider={provider};"
            f"symbols={','.join(symbols)}"
        ),
        recommended_action="runbook:RUN-DATA-05#processing_fallback",
    )


def _log_sla_entry(
    *,
    provider: str,
    timeframe: str,
    symbols: Sequence[str],
    symbol: str | None = None,
    stage: str,
    p95_ms: float,
    p99_ms: float,
    bars: int,
    status: str | None,
    rate_limit_ratio: float = 0.0,
    latency_status: str | None = None,
    quality_flag: int | None = None,
    last_bar_ts: str | None = None,
    bar_gap_minutes: int | None = None,
    delay_sec: float | None = None,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    timestamp: str | None = None,
) -> None:
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    status = status or _compute_latency_status(p95_ms)
    latency_status = latency_status or status
    payload = {
        "ts": timestamp or _utcnow_iso(),
        "provider": provider,
        "stage": stage,
        "phase": stage,
        "timeframe": timeframe,
        "symbols": list(symbols),
        "fetch_p95_ms": float(p95_ms),
        "fetch_p99_ms": float(p99_ms),
        "bars": bars,
        "429_rate": float(rate_limit_ratio),
        "latency_status": latency_status,
    }
    if status is not None:
        payload["status"] = status
    if symbol is not None:
        payload["symbol"] = symbol
    if quality_flag is not None:
        payload["quality_flag"] = int(quality_flag)
    if last_bar_ts is not None:
        payload["last_bar_ts"] = last_bar_ts
    if bar_gap_minutes is not None:
        payload["bar_gap_minutes"] = int(bar_gap_minutes)
    if delay_sec is not None:
        payload["delay_sec"] = float(delay_sec)
        if stage == "fetch":
            payload["fetch_delay_sec"] = float(delay_sec)
        elif stage == "processing":
            payload["processing_delay_sec"] = float(delay_sec)
    try:
        with metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
    except OSError:
        pass


def log_processing_delay(
    *,
    provider: str,
    timeframe: str,
    symbol: str,
    bars: int,
    processing_ms: float,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    health_monitor: HealthMonitor | None = None,
    processing_delay_warn_sec: float = 12.0,
    processing_delay_breach_sec: float | None = None,
    timestamp: str | None = None,
) -> None:
    delay_sec = max(float(processing_ms) / 1000.0, 0.0)
    _maybe_raise_processing_latency(
        health_monitor,
        delay_sec=delay_sec,
        provider=provider,
        symbols=[symbol],
        processing_delay_warn_sec=processing_delay_warn_sec,
    )
    warn_ms = processing_delay_warn_sec * 1000.0
    breach_sec = (
        processing_delay_breach_sec
        if processing_delay_breach_sec is not None
        else processing_delay_warn_sec * 1.5
    )
    status = _compute_latency_status(processing_ms, warn_ms=warn_ms, breach_ms=breach_sec * 1000.0)
    _log_sla_entry(
        provider=provider,
        timeframe=timeframe,
        symbols=[symbol],
        symbol=symbol,
        stage="processing",
        p95_ms=processing_ms,
        p99_ms=processing_ms,
        bars=bars,
        status=status,
        rate_limit_ratio=0.0,
        metrics_path=metrics_path,
        delay_sec=delay_sec,
        timestamp=timestamp,
    )


def _log_stage_eval(decision: StageDecision, *, log_path: Path | None) -> None:
    if not log_path:
        return
    payload = {
        "ts": _utcnow_iso(),
        "provider": decision.provider,
        "stage_eval": decision.to_mapping(),
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
    except OSError:
        pass


def _evaluate_rate_limit(
    *,
    provider: str,
    rate_limit_ratio: float,
    guard: RateLimitGuard,
    state: Mapping[str, str],
    log_path: Path | None,
    decision_source: str | None = None,
    runbook_ref: str | None = None,
) -> StageDecision:
    current_stage = state.get(provider)
    decision = guard.evaluate(
        provider=provider,
        rate_429=rate_limit_ratio,
        current_stage=current_stage,
        decision_source=decision_source,
        runbook_ref=runbook_ref,
    )
    _log_stage_eval(decision, log_path=log_path)
    return decision


def _load_rate_limit_state(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(k): str(v) for k, v in payload.items()}


def _persist_rate_limit_state(path: Path | None, state: Mapping[str, str]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(state, ensure_ascii=False, indent=2))


def _append_bar_ready(
    frames: Sequence[MarketFrame],
    *,
    path: Path | None = None,
    source: str | None = None,
) -> None:
    if not frames:
        return
    resolved = path or Path(
        os.getenv("TRADECTL_BAR_READY_QUEUE", str(DEFAULT_BAR_READY_QUEUE))
    )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    ts = _utcnow_iso()
    try:
        with resolved.open("a", encoding="utf-8") as handle:
            for frame in frames:
                payload = {
                    "event": "bar.ready",
                    "ts": ts,
                    "symbol": frame.symbol,
                    "timeframe": frame.timeframe,
                    "bars": frame.bars,
                    "bar_count": len(frame.bars),
                    "quality_flag": frame.quality_flag,
                    "source": source or "ingestion",
                }
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
    except OSError:
        return


def _compute_latency_status(
    p95_ms: float, *, warn_ms: float = 1_000.0, breach_ms: float = 1_500.0
) -> str:
    """Coarse latency health classification."""

    if p95_ms >= breach_ms:
        return "breach"
    if p95_ms >= warn_ms:
        return "watch"
    return "ok"


def load_provider_sla_thresholds(path: Path) -> Mapping[str, tuple[float, float]]:
    """Load provider-specific SLA thresholds from JSON/YAML."""

    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    raw = None
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            raw = None
    if raw is None:
        try:
            raw = yaml.safe_load(text)
        except Exception:
            logger.error("data.sla_thresholds.invalid_json", extra={"path": str(path)})
            return {}
    if not isinstance(raw, dict):
        return {}
    if "providers" in raw and isinstance(raw["providers"], dict):
        raw = raw["providers"]
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
    try:
        result = handler(symbols, timeframe)
    except Exception as exc:
        raise ProviderError(f"provider {provider} failed: {exc}") from exc
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
    start: str | None = None,
    end: str | None = None,
    provider_priority: Sequence[str] | None = None,
    context: object | None = None,
    retries: int = 2,
    backoff_ms: float = 500.0,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    provider_handlers: dict[str, Callable[[Sequence[str], str], ProviderResult | list[MarketFrame]]]
    | None = None,
    provider_profiles: Mapping[str, Any] | None = None,
    warn_ms: float = 1_000.0,
    breach_ms: float = 1_500.0,
    provider_sla_thresholds: Mapping[str, tuple[float, float]] | None = None,
    metrics_collector: IngestionMetricsCollector | None = None,
    data_quality_guard: DataQualityGuard | None = None,
    rate_limit_guard: RateLimitGuard | None = None,
    rate_limit_state: dict[str, str] | None = None,
    rate_limit_log_path: Path | None = None,
    rate_limit_state_path: Path | None = None,
    auto_apply_rate_limit_stage: bool = False,
    rate_limit_decision_source: str | None = None,
    rate_limit_runbook_ref: str | None = None,
    worker_plan: WorkerPlan | None = None,
    apply_worker_plan: bool = False,
    health_monitor: HealthMonitor | None = None,
    buffer_coordinator: BufferCoordinator | None = None,
    fetch_delay_warn_sec: float = 18.0,
    bar_gap_warn_minutes: int = 10,
    processing_delay_warn_sec: float = 12.0,
    processing_delay_breach_sec: float | None = None,
    fallback_log_path: Path | None = None,
    fallback_queue: Any | None = None,
) -> list[MarketFrame]:
    """Fetch the most recent bars for the requested symbols and log SLA metrics."""

    _ = context  # reserved for future wiring
    priorities = load_ingestion_priorities()
    symbols = order_symbols_by_priority(symbols, timeframe=timeframe, priorities=priorities)
    providers = resolve_provider_priority(symbols, provider_priority=provider_priority)
    primary_provider = providers[0] if providers else "primary"
    frames: list[MarketFrame] = []
    if provider_profiles is None:
        provider_profiles = load_provider_profiles()
    handler_map = provider_handlers or build_provider_handlers(
        timeframe=timeframe,
        start=start,
        end=end,
        provider_profiles=provider_profiles,
    )
    provider_sla_thresholds = provider_sla_thresholds or {}
    rate_limit_state = (
        rate_limit_state
        if rate_limit_state is not None
        else _load_rate_limit_state(rate_limit_state_path)
    )
    buffer_coordinator = buffer_coordinator or DEFAULT_BUFFER_COORDINATOR
    fallback_log_path = DEFAULT_FALLBACK_LOG if fallback_log_path is None else fallback_log_path
    provider_plans: Mapping[str, WorkerPlan] = {}
    if rate_limit_guard:
        for provider in providers:
            plan = rate_limit_guard.worker_plan(
                provider=provider, stage=rate_limit_state.get(provider)
            )
            provider_plans[provider] = WorkerPlan(
                provider=provider,
                stage=plan["stage"],
                poll_interval_sec=float(plan["poll_interval_sec"]),
                max_workers=int(plan["max_workers"]),
            )

    def _enqueue_fallback_task(task: FallbackRetryTask) -> None:
        if fallback_queue is None:
            return
        enqueue = getattr(fallback_queue, "enqueue", None)
        if not callable(enqueue):
            return
        try:
            result = enqueue(task)
        except Exception as exc:
            logger.debug("data.fetch_latest.enqueue_failed", extra={"error": str(exc)})
            return
        if inspect.isawaitable(result):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(result)
            else:
                loop.create_task(result)

    def _emit_fallback_state(**kwargs: Any) -> None:
        if fallback_log_path is not None:
            record_fallback_event(path=fallback_log_path, **kwargs)
        _enqueue_fallback_task(FallbackRetryTask(**kwargs))

    def _fetch_provider_once(
        provider: str,
        current_plan: WorkerPlan | None = None,
        *,
        retries_for_provider: int,
        backoff_ms_for_provider: float,
    ) -> tuple[list[MarketFrame], float]:
        local_frames: list[MarketFrame] = []
        retry_budget = retries_for_provider
        attempt = 0
        warn = provider_sla_thresholds.get(provider, (warn_ms, breach_ms))[0]
        breach = provider_sla_thresholds.get(provider, (warn_ms, breach_ms))[1]
        rate_limit_ratio = 0.0
        quality_flag = 0
        max_attempts = retry_budget + 1
        while retry_budget >= 0:
            buffer_item: BufferItem | None = None
            try:
                request_ts = datetime.now(timezone.utc)
                start = time.perf_counter()
                result = _invoke_provider(
                    provider=provider,
                    symbols=symbols,
                    timeframe=timeframe,
                    handler=handler_map.get(provider),
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                local_frames = result.frames
                buffer_item = buffer_coordinator.enqueue(
                    provider=provider,
                    symbols=symbols,
                    timeframe=timeframe,
                    request_ts=request_ts,
                    frames=local_frames,
                )
                delay_sec = max(
                    (buffer_item.enqueue_ts - buffer_item.request_ts).total_seconds(), 0.0
                )
                processing_start = time.perf_counter()
                if data_quality_guard:
                    for frame in local_frames:
                        quality = data_quality_guard.validate(frame)
                        quality_flag = max(quality_flag, quality.quality_flag)
                        if quality.status in {"fail", "error"}:
                            raise DataQualityError(
                                f"data_quality_failed: {quality.issues}",
                                details={
                                    "issues": quality.issues,
                                    "status": quality.status,
                                    "quality_flag": quality.quality_flag,
                                    "clock_drift_ms": quality.clock_drift_ms,
                                    "missing_ratio": quality.missing_ratio,
                                    "provider": provider,
                                    "manual_csv_required": provider == primary_provider,
                                },
                            )
                processing_ms = (time.perf_counter() - processing_start) * 1000
                processing_delay_ms = max(
                    (datetime.now(timezone.utc) - buffer_item.enqueue_ts).total_seconds()
                    * 1000.0,
                    0.0,
                )
                buffer_coordinator.pop()
                rate_limit_ratio = result.rate_limit_ratio
                p95_ms = result.p95_ms
                p99_ms = result.p99_ms
                if metrics_collector:
                    metrics_collector.observe(
                        provider=provider,
                        symbols=symbols,
                        timeframe=timeframe,
                        latency_ms=elapsed_ms,
                        bars=len(local_frames),
                        stage="fetch",
                        rate_limit_ratio=rate_limit_ratio,
                        success=True,
                    )
                    snapshot = metrics_collector.snapshot()
                    p95_ms = snapshot.get("fetch_p95_ms") or p95_ms
                    p99_ms = snapshot.get("fetch_p99_ms") or p99_ms
                anchor = _parse_bar_timestamp(end) or datetime.now(timezone.utc)
                last_ts = _extract_last_bar_timestamp(local_frames)
                last_bar_ts = (
                    last_ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")
                    if last_ts
                    else None
                )
                bar_gap_minutes = _compute_bar_gap_minutes(anchor, last_ts)
                _maybe_raise_data_latency(
                    health_monitor,
                    delay_sec=delay_sec,
                    bar_gap_minutes=bar_gap_minutes,
                    provider=provider,
                    symbols=symbols,
                    fetch_delay_warn_sec=fetch_delay_warn_sec,
                    bar_gap_warn_minutes=bar_gap_warn_minutes,
                )
                _log_sla_entry(
                    provider=provider,
                    timeframe=timeframe,
                    symbols=symbols,
                    stage="fetch",
                    p95_ms=p95_ms,
                    p99_ms=p99_ms,
                    bars=len(local_frames),
                    status=_compute_latency_status(p95_ms, warn_ms=warn, breach_ms=breach),
                    rate_limit_ratio=rate_limit_ratio,
                    metrics_path=metrics_path,
                    quality_flag=quality_flag,
                    last_bar_ts=last_bar_ts,
                    bar_gap_minutes=bar_gap_minutes,
                    delay_sec=delay_sec,
                )
                logger.info(
                    "data.fetch",
                    extra={
                        "provider": provider,
                        "symbols": list(symbols),
                        "timeframe": timeframe,
                        "attempt": attempt,
                        "latency_ms": round(float(elapsed_ms), 3),
                        "bars": len(local_frames),
                        "rate_limit_ratio": rate_limit_ratio,
                        "status": "ok",
                    },
                )
                if local_frames:
                    for frame in local_frames:
                        log_processing_delay(
                            provider=provider,
                            timeframe=timeframe,
                            symbol=frame.symbol,
                            bars=len(frame.bars),
                            processing_ms=processing_delay_ms,
                            metrics_path=metrics_path,
                            health_monitor=health_monitor,
                            processing_delay_warn_sec=processing_delay_warn_sec,
                            processing_delay_breach_sec=processing_delay_breach_sec,
                        )
                break
            except (ProviderError, DataQualityError) as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000 if "start" in locals() else 0.0
                local_frames = []
                if buffer_item is not None:
                    buffer_coordinator.pop()
                if metrics_collector:
                    metrics_collector.observe(
                        provider=provider,
                        symbols=symbols,
                        timeframe=timeframe,
                        latency_ms=elapsed_ms,
                        bars=0,
                        stage="fetch",
                        rate_limit_ratio=getattr(exc, "rate_limit_ratio", 0.0),
                        success=False,
                    )
                if isinstance(exc, DataQualityError):
                    quality_flag = max(
                        quality_flag, int(exc.details.get("quality_flag", 0) or 0)
                    )
                logger.info(
                    "data.fetch_failed",
                    extra={
                        "provider": provider,
                        "symbols": list(symbols),
                        "timeframe": timeframe,
                        "attempt": attempt,
                        "error": str(exc),
                        "status": "error",
                    },
                )
                logger.warning(
                    "data.fetch_latest.retry provider=%s error=%s attempt=%s",
                    provider,
                    str(exc),
                    attempt,
                )
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
                    quality_flag=quality_flag,
                )
                retry_budget -= 1
                attempt += 1
                if retry_budget >= 0 and fallback_log_path is not None:
                    _emit_fallback_state(
                        provider=provider,
                        symbols=symbols,
                        timeframe=timeframe,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        state="retry_scheduled",
                        reason=str(exc),
                        stage="fetch_latest",
                    )
                if retry_budget < 0:
                    break
                current_plan_for_backoff = current_plan or provider_plans.get(provider)
                backoff_base = (
                    current_plan_for_backoff.poll_interval_sec * 1000
                    if current_plan_for_backoff
                    else backoff_ms_for_provider
                )
                delay_ms = backoff_base if attempt == 1 else backoff_base * 2
                if fallback_log_path is not None:
                    _emit_fallback_state(
                        provider=provider,
                        symbols=symbols,
                        timeframe=timeframe,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        state="retry_backoff",
                        backoff_sec=delay_ms / 1000.0,
                        reason=str(exc),
                        stage="fetch_latest",
                    )
                logger.info(
                    "data.fetch_latest.backoff", extra={"delay_ms": delay_ms, "provider": provider}
                )
                time.sleep(max(delay_ms / 1000.0, 0.0))
            except Exception as exc:  # pragma: no cover - defensive
                if buffer_item is not None:
                    buffer_coordinator.pop()
                logger.error("data.fetch_latest.unexpected", extra={"error": str(exc)})
                break
        if not local_frames and fallback_log_path is not None:
            _emit_fallback_state(
                provider=provider,
                symbols=symbols,
                timeframe=timeframe,
                attempt=attempt,
                max_attempts=max_attempts,
                state="retry_exhausted",
                reason="no_frames",
                stage="fetch_latest",
            )
        return local_frames, rate_limit_ratio

    if apply_worker_plan:
        plans: list[WorkerPlan] = list(provider_plans.values())
        if worker_plan and not plans:
            plans = [
                WorkerPlan(
                    provider=p,
                    stage=worker_plan.stage,
                    poll_interval_sec=worker_plan.poll_interval_sec,
                    max_workers=worker_plan.max_workers,
                )
                for p in providers
            ]
        if not plans:
            plans = spawn_provider_workers(
                providers=providers,
                rate_limit_guard=rate_limit_guard,
                rate_limit_state=rate_limit_state,
            )
        plan_lookup = {plan.provider: plan for plan in plans}
        result_frames: dict[str, list[MarketFrame]] = {}

        def _make_job(target_provider: str) -> Callable[[], None]:
            def _job() -> None:
                retries_for_provider, backoff_ms_for_provider = _resolve_retry_settings(
                    target_provider,
                    provider_profiles,
                    default_retries=retries,
                    default_backoff_ms=backoff_ms,
                )
                frames_for_provider, rl_ratio = _fetch_provider_once(
                    target_provider,
                    plan_lookup.get(target_provider),
                    retries_for_provider=retries_for_provider,
                    backoff_ms_for_provider=backoff_ms_for_provider,
                )
                result_frames[target_provider] = frames_for_provider
                if rate_limit_guard:
                    decision = _evaluate_rate_limit(
                        provider=target_provider,
                        rate_limit_ratio=rl_ratio,
                        guard=rate_limit_guard,
                        state=rate_limit_state,
                        log_path=rate_limit_log_path,
                        decision_source=rate_limit_decision_source,
                        runbook_ref=rate_limit_runbook_ref,
                    )
                    if auto_apply_rate_limit_stage:
                        rate_limit_state[target_provider] = decision.stage

            return _job

        job_queue = [(provider, _make_job(provider)) for provider in providers]
        run_fetch_workers(plans=plans, queue=job_queue, iterations=1, stop_when_empty=False)
        for provider in providers:
            frames = result_frames.get(provider)
            if frames:
                return frames
        return []

    quality_flag = 0
    for index, provider in enumerate(providers):
        retries_for_provider, backoff_ms_for_provider = _resolve_retry_settings(
            provider,
            provider_profiles,
            default_retries=retries,
            default_backoff_ms=backoff_ms,
        )
        retry_budget = retries_for_provider
        attempt = 0
        warn = provider_sla_thresholds.get(provider, (warn_ms, breach_ms))[0]
        breach = provider_sla_thresholds.get(provider, (warn_ms, breach_ms))[1]
        quality_flag = 0
        max_attempts = retry_budget + 1
        while retry_budget >= 0:
            try:
                buffer_item: BufferItem | None = None
                request_ts = datetime.now(timezone.utc)
                start = time.perf_counter()
                result = _invoke_provider(
                    provider=provider,
                    symbols=symbols,
                    timeframe=timeframe,
                    handler=handler_map.get(provider),
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                frames = result.frames
                buffer_item = buffer_coordinator.enqueue(
                    provider=provider,
                    symbols=symbols,
                    timeframe=timeframe,
                    request_ts=request_ts,
                    frames=frames,
                )
                delay_sec = max(
                    (buffer_item.enqueue_ts - buffer_item.request_ts).total_seconds(), 0.0
                )
                processing_start = time.perf_counter()
                if data_quality_guard:
                    for frame in frames:
                        quality = data_quality_guard.validate(frame)
                        quality_flag = max(quality_flag, quality.quality_flag)
                        if quality.status in {"fail", "error"}:
                            raise DataQualityError(
                                f"data_quality_failed: {quality.issues}",
                                details={
                                    "issues": quality.issues,
                                    "status": quality.status,
                                    "quality_flag": quality.quality_flag,
                                    "clock_drift_ms": quality.clock_drift_ms,
                                    "missing_ratio": quality.missing_ratio,
                                    "provider": provider,
                                    "manual_csv_required": provider == primary_provider,
                                },
                            )
                processing_ms = (time.perf_counter() - processing_start) * 1000
                processing_delay_ms = processing_ms
                if buffer_item is not None:
                    processing_delay_ms = max(
                        (datetime.now(timezone.utc) - buffer_item.enqueue_ts).total_seconds()
                        * 1000.0,
                        0.0,
                    )
                    buffer_coordinator.pop()
                p95_ms = result.p95_ms
                p99_ms = result.p99_ms
                if metrics_collector:
                    metrics_collector.observe(
                        provider=provider,
                        symbols=symbols,
                        timeframe=timeframe,
                        latency_ms=elapsed_ms,
                        bars=len(frames),
                        stage="fetch",
                        rate_limit_ratio=result.rate_limit_ratio,
                        success=True,
                    )
                    snapshot = metrics_collector.snapshot()
                    p95_ms = snapshot.get("fetch_p95_ms") or p95_ms
                    p99_ms = snapshot.get("fetch_p99_ms") or p99_ms
                anchor = _parse_bar_timestamp(end) or datetime.now(timezone.utc)
                last_ts = _extract_last_bar_timestamp(frames)
                last_bar_ts = (
                    last_ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")
                    if last_ts
                    else None
                )
                bar_gap_minutes = _compute_bar_gap_minutes(anchor, last_ts)
                _maybe_raise_data_latency(
                    health_monitor,
                    delay_sec=delay_sec,
                    bar_gap_minutes=bar_gap_minutes,
                    provider=provider,
                    symbols=symbols,
                    fetch_delay_warn_sec=fetch_delay_warn_sec,
                    bar_gap_warn_minutes=bar_gap_warn_minutes,
                )
                _log_sla_entry(
                    provider=provider,
                    timeframe=timeframe,
                    symbols=symbols,
                    stage="fetch",
                    p95_ms=p95_ms,
                    p99_ms=p99_ms,
                    bars=len(frames),
                    status=_compute_latency_status(p95_ms, warn_ms=warn, breach_ms=breach),
                    rate_limit_ratio=result.rate_limit_ratio,
                    metrics_path=metrics_path,
                    quality_flag=quality_flag,
                    last_bar_ts=last_bar_ts,
                    bar_gap_minutes=bar_gap_minutes,
                    delay_sec=delay_sec,
                )
                logger.info(
                    "data.fetch",
                    extra={
                        "provider": provider,
                        "symbols": list(symbols),
                        "timeframe": timeframe,
                        "attempt": attempt,
                        "latency_ms": round(float(elapsed_ms), 3),
                        "bars": len(frames),
                        "rate_limit_ratio": result.rate_limit_ratio,
                        "status": "ok",
                    },
                )
                if frames:
                    for frame in frames:
                        log_processing_delay(
                            provider=provider,
                            timeframe=timeframe,
                            symbol=frame.symbol,
                            bars=len(frame.bars),
                            processing_ms=processing_delay_ms,
                            metrics_path=metrics_path,
                            health_monitor=health_monitor,
                            processing_delay_warn_sec=processing_delay_warn_sec,
                            processing_delay_breach_sec=processing_delay_breach_sec,
                        )
                break
            except (ProviderError, DataQualityError) as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000 if "start" in locals() else 0.0
                frames = []
                if buffer_item is not None:
                    buffer_coordinator.pop()
                if metrics_collector:
                    metrics_collector.observe(
                        provider=provider,
                        symbols=symbols,
                        timeframe=timeframe,
                        latency_ms=elapsed_ms,
                        bars=0,
                        stage="fetch",
                        rate_limit_ratio=getattr(exc, "rate_limit_ratio", 0.0),
                        success=False,
                    )
                if isinstance(exc, DataQualityError):
                    quality_flag = max(
                        quality_flag, int(exc.details.get("quality_flag", 0) or 0)
                    )
                logger.info(
                    "data.fetch_failed",
                    extra={
                        "provider": provider,
                        "symbols": list(symbols),
                        "timeframe": timeframe,
                        "attempt": attempt,
                        "error": str(exc),
                        "status": "error",
                    },
                )
                logger.warning(
                    "data.fetch_latest.retry provider=%s error=%s attempt=%s",
                    provider,
                    str(exc),
                    attempt,
                )
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
                    quality_flag=quality_flag,
                )
                retry_budget -= 1
                attempt += 1
                if retry_budget >= 0 and fallback_log_path is not None:
                    _emit_fallback_state(
                        provider=provider,
                        symbols=symbols,
                        timeframe=timeframe,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        state="retry_scheduled",
                        reason=str(exc),
                        stage="fetch_latest",
                    )
                if retry_budget < 0:
                    break
                current_plan = provider_plans.get(provider) if provider_plans else worker_plan
                backoff_base = (
                    current_plan.poll_interval_sec * 1000 if current_plan else backoff_ms_for_provider
                )
                delay_ms = backoff_base if attempt == 1 else backoff_base * 2
                if fallback_log_path is not None:
                    _emit_fallback_state(
                        provider=provider,
                        symbols=symbols,
                        timeframe=timeframe,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        state="retry_backoff",
                        backoff_sec=delay_ms / 1000.0,
                        reason=str(exc),
                        stage="fetch_latest",
                    )
                logger.info(
                    "data.fetch_latest.backoff", extra={"delay_ms": delay_ms, "provider": provider}
                )
                time.sleep(max(delay_ms / 1000.0, 0.0))
                # placeholder: in async/real mode use asyncio.sleep(delay_ms/1000)
            except Exception as exc:  # pragma: no cover - defensive
                if buffer_item is not None:
                    buffer_coordinator.pop()
                logger.error("data.fetch_latest.unexpected", extra={"error": str(exc)})
                break
        # evaluate rate limit guard for this provider
        if frames and rate_limit_guard:
            decision = _evaluate_rate_limit(
                provider=provider,
                rate_limit_ratio=result.rate_limit_ratio if "result" in locals() else 0.0,
                guard=rate_limit_guard,
                state=rate_limit_state,
                log_path=rate_limit_log_path,
                decision_source=rate_limit_decision_source,
                runbook_ref=rate_limit_runbook_ref,
            )
            if auto_apply_rate_limit_stage:
                rate_limit_state[provider] = decision.stage
            if decision.decision == "rollback" and provider != providers[-1]:
                frames = []
                logger.info(
                    "data.fetch_latest.failover_rate_limit",
                    extra={"from": provider, "reason": "rate_limit_high"},
                )
                if fallback_log_path is not None:
                    _emit_fallback_state(
                        provider=provider,
                        symbols=symbols,
                        timeframe=timeframe,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        state="failover_to",
                        reason="rate_limit_high",
                        failover_to=providers[index + 1],
                        stage="fetch_latest",
                    )
                continue
        if not frames and fallback_log_path is not None:
            failover_to = providers[index + 1] if index + 1 < len(providers) else None
            state = "failover_to" if failover_to else "failed"
            _emit_fallback_state(
                provider=provider,
                symbols=symbols,
                timeframe=timeframe,
                attempt=attempt,
                max_attempts=max_attempts,
                state=state,
                reason="no_frames",
                failover_to=failover_to,
                stage="fetch_latest",
            )
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
            quality_flag=quality_flag if providers else None,
        )
    if auto_apply_rate_limit_stage:
        _persist_rate_limit_state(rate_limit_state_path, rate_limit_state)
    _append_bar_ready(frames, source="fetch_latest")
    return frames


def backfill(
    symbols: Sequence[str],
    timeframe: str,
    start: str,
    end: str,
    *,
    priority: str | None = None,
    provider_priority: Sequence[str] | None = None,
    provider_handlers: Mapping[str, Callable[[Sequence[str], str], ProviderResult | list[MarketFrame]]]
    | None = None,
    context: object | None = None,
    retries: int = 2,
    backoff_ms: float = 500.0,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    provider_profiles: Mapping[str, Any] | None = None,
    warn_ms: float = 1_000.0,
    breach_ms: float = 1_500.0,
    provider_sla_thresholds: Mapping[str, tuple[float, float]] | None = None,
    data_quality_guard: DataQualityGuard | None = None,
    metrics_collector: IngestionMetricsCollector | None = None,
    health_monitor: HealthMonitor | None = None,
    buffer_coordinator: BufferCoordinator | None = None,
    fetch_delay_warn_sec: float = 18.0,
    bar_gap_warn_minutes: int = 10,
    processing_delay_warn_sec: float = 12.0,
    processing_delay_breach_sec: float | None = None,
    chunk_hours: int = 6,
) -> BackfillResult:
    """Backfill the requested window for the given symbols."""

    _ = context
    start_dt = _parse_bar_timestamp(start)
    end_dt = _parse_bar_timestamp(end)
    if start_dt is None or end_dt is None:
        raise BackfillRangeError("backfill range must be valid ISO timestamps")
    if end_dt <= start_dt:
        raise BackfillRangeError("backfill end must be after start")

    provider_sla_thresholds = provider_sla_thresholds or {}
    buffer_coordinator = buffer_coordinator or DEFAULT_BUFFER_COORDINATOR
    if provider_profiles is None:
        provider_profiles = load_provider_profiles()
    priorities = load_ingestion_priorities()
    ordered_symbols = order_symbols_by_priority(symbols, timeframe=timeframe, priorities=priorities)
    providers = resolve_provider_priority(ordered_symbols, provider_priority=provider_priority)
    frames_by_symbol: dict[str, list[dict[str, object]]] = {}
    quality_flags: dict[str, int] = {}
    provider_used: str | None = None
    total_retries = 0

    for chunk_start, chunk_end in _chunk_backfill_ranges(start_dt, end_dt, chunk_hours=chunk_hours):
        handler_map = provider_handlers or build_provider_handlers(
            timeframe=timeframe,
            start=chunk_start.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            end=chunk_end.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            provider_profiles=provider_profiles,
        )
        success = False
        for provider in providers:
            retries_for_provider, backoff_ms_for_provider = _resolve_retry_settings(
                provider,
                provider_profiles,
                default_retries=retries,
                default_backoff_ms=backoff_ms,
            )
            warn, breach = provider_sla_thresholds.get(provider, (warn_ms, breach_ms))
            retry_budget = retries_for_provider
            attempt = 0
            while retry_budget >= 0:
                try:
                    buffer_item: BufferItem | None = None
                    request_ts = datetime.now(timezone.utc)
                    fetch_start = time.perf_counter()
                    result = _invoke_provider(
                        provider=provider,
                        symbols=ordered_symbols,
                        timeframe=timeframe,
                        handler=handler_map.get(provider),
                    )
                    fetch_elapsed_ms = (time.perf_counter() - fetch_start) * 1000
                    frames = result.frames
                    buffer_item = buffer_coordinator.enqueue(
                        provider=provider,
                        symbols=ordered_symbols,
                        timeframe=timeframe,
                        request_ts=request_ts,
                        frames=frames,
                    )
                    delay_sec = max(
                        (buffer_item.enqueue_ts - buffer_item.request_ts).total_seconds(), 0.0
                    )
                    processing_start = time.perf_counter()
                    if data_quality_guard:
                        for frame in frames:
                            quality = data_quality_guard.validate(frame)
                            quality_flags[frame.symbol] = max(
                                quality_flags.get(frame.symbol, 0),
                                quality.quality_flag,
                            )
                            if quality.status in {"fail", "error"}:
                                raise DataQualityError(
                                    f"data_quality_failed: {quality.issues}",
                                    details={
                                        "issues": quality.issues,
                                        "status": quality.status,
                                        "quality_flag": quality.quality_flag,
                                },
                            )
                    processing_ms = (time.perf_counter() - processing_start) * 1000
                    processing_delay_ms = processing_ms
                    if buffer_item is not None:
                        processing_delay_ms = max(
                            (datetime.now(timezone.utc) - buffer_item.enqueue_ts).total_seconds()
                            * 1000.0,
                            0.0,
                        )
                        buffer_coordinator.pop()
                    p95_ms = result.p95_ms
                    p99_ms = result.p99_ms
                    if metrics_collector:
                        metrics_collector.observe(
                            provider=provider,
                            symbols=ordered_symbols,
                            timeframe=timeframe,
                            latency_ms=fetch_elapsed_ms,
                            bars=sum(len(frame.bars) for frame in frames),
                            stage="backfill",
                            rate_limit_ratio=result.rate_limit_ratio,
                            success=True,
                        )
                        snapshot = metrics_collector.snapshot()
                        p95_ms = snapshot.get("fetch_p95_ms") or p95_ms
                        p99_ms = snapshot.get("fetch_p99_ms") or p99_ms
                    last_ts = _extract_last_bar_timestamp(frames)
                    last_bar_ts = (
                        last_ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")
                        if last_ts
                        else None
                    )
                    bar_gap_minutes = _compute_bar_gap_minutes(chunk_end, last_ts)
                    _maybe_raise_data_latency(
                        health_monitor,
                        delay_sec=delay_sec,
                        bar_gap_minutes=bar_gap_minutes,
                        provider=provider,
                        symbols=ordered_symbols,
                        fetch_delay_warn_sec=fetch_delay_warn_sec,
                        bar_gap_warn_minutes=bar_gap_warn_minutes,
                    )
                    _log_sla_entry(
                        provider=provider,
                        timeframe=timeframe,
                        symbols=ordered_symbols,
                        stage="backfill",
                        p95_ms=p95_ms,
                        p99_ms=p99_ms,
                        bars=sum(len(frame.bars) for frame in frames),
                        status=_compute_latency_status(p95_ms, warn_ms=warn, breach_ms=breach),
                        rate_limit_ratio=result.rate_limit_ratio,
                        metrics_path=metrics_path,
                        quality_flag=max(quality_flags.values(), default=0),
                        last_bar_ts=last_bar_ts,
                        bar_gap_minutes=bar_gap_minutes,
                        delay_sec=delay_sec,
                    )
                    if frames:
                        for frame in frames:
                            log_processing_delay(
                                provider=provider,
                                timeframe=timeframe,
                                symbol=frame.symbol,
                                bars=len(frame.bars),
                                processing_ms=processing_delay_ms,
                                metrics_path=metrics_path,
                                health_monitor=health_monitor,
                                processing_delay_warn_sec=processing_delay_warn_sec,
                                processing_delay_breach_sec=processing_delay_breach_sec,
                            )
                    for frame in frames:
                        frames_by_symbol.setdefault(frame.symbol, []).extend(frame.bars)
                        quality_flags[frame.symbol] = max(
                            quality_flags.get(frame.symbol, 0),
                            frame.quality_flag,
                        )
                    provider_used = provider
                    success = True
                    break
                except (ProviderError, DataQualityError) as exc:
                    total_retries += 1
                    fetch_elapsed_ms = (
                        (time.perf_counter() - fetch_start) * 1000 if "fetch_start" in locals() else 0
                    )
                    if buffer_item is not None:
                        buffer_coordinator.pop()
                    if metrics_collector:
                        metrics_collector.observe(
                            provider=provider,
                            symbols=ordered_symbols,
                            timeframe=timeframe,
                            latency_ms=fetch_elapsed_ms,
                            bars=0,
                            stage="backfill",
                            rate_limit_ratio=getattr(exc, "rate_limit_ratio", 0.0),
                            success=False,
                        )
                    if isinstance(exc, DataQualityError):
                        for symbol in ordered_symbols:
                            quality_flags[symbol] = max(
                                quality_flags.get(symbol, 0),
                                int(exc.details.get("quality_flag", 0) or 0),
                            )
                    logger.warning(
                        "data.backfill.retry provider=%s error=%s attempt=%s",
                        provider,
                        str(exc),
                        attempt,
                    )
                    _log_sla_entry(
                        provider=provider,
                        timeframe=timeframe,
                        symbols=ordered_symbols,
                        stage="backfill",
                        p95_ms=0.0,
                        p99_ms=0.0,
                        bars=0,
                        status="error",
                        rate_limit_ratio=getattr(exc, "rate_limit_ratio", 0.0),
                        metrics_path=metrics_path,
                        quality_flag=max(quality_flags.values(), default=0),
                    )
                    retry_budget -= 1
                    attempt += 1
                    if retry_budget < 0:
                        break
                    delay_ms = (
                        backoff_ms_for_provider if attempt == 1 else backoff_ms_for_provider * 2
                    )
                    time.sleep(max(delay_ms / 1000.0, 0.0))
                except Exception as exc:  # pragma: no cover - defensive
                    if buffer_item is not None:
                        buffer_coordinator.pop()
                    logger.error("data.backfill.unexpected", extra={"error": str(exc)})
                    retry_budget = -1
            if success:
                break
        if not success:
            raise BackfillFailedError(
                f"backfill failed for {chunk_start.isoformat()}..{chunk_end.isoformat()}"
            )

    frames: list[MarketFrame] = []
    for symbol in ordered_symbols:
        bars = frames_by_symbol.get(symbol, [])
        frames.append(
            MarketFrame(
                symbol=symbol,
                timeframe=timeframe,
                bars=bars,
                quality_flag=quality_flags.get(symbol, 0),
            )
        )
    _append_bar_ready(frames, source=f"backfill:{provider_used or priority or 'unknown'}")
    return BackfillResult(
        frames=frames,
        provider_used=provider_used or priority,
        retry_count=total_retries,
        status="ok",
    )


def warm_cache(*, context: object | None = None) -> None:
    """Preload provider caches at service startup."""

    _ = context


def spawn_provider_workers(
    *,
    providers: Sequence[str] | None = None,
    rate_limit_guard: RateLimitGuard | None = None,
    rate_limit_state: Mapping[str, str] | None = None,
    default_poll_interval: float = 15.0,
    default_max_workers: int = 4,
    catch_up_mode: bool | None = None,
    max_workers_normal: int | None = None,
    max_workers_catch_up: int | None = None,
    runbook_ref: str | None = None,
    ops_worklog_path: Path | None = None,
) -> list[WorkerPlan]:
    """Return worker plans (poll interval/max workers) per provider."""

    plans: list[WorkerPlan] = []
    rate_limit_state = rate_limit_state or {}
    if catch_up_mode is None:
        catch_up_mode = _truthy_env("TRADECTL_CATCH_UP_MODE")
    if max_workers_normal is None:
        max_workers_normal = _read_int_env("TRADECTL_MAX_WORKERS_NORMAL", DEFAULT_MAX_WORKERS_NORMAL)
    if max_workers_catch_up is None:
        max_workers_catch_up = _read_int_env(
            "TRADECTL_MAX_WORKERS_CATCH_UP", DEFAULT_MAX_WORKERS_CATCH_UP
        )
    target_max_workers = max_workers_catch_up if catch_up_mode else max_workers_normal
    ops_worklog_path = ops_worklog_path or DEFAULT_OPS_WORKLOG_PATH
    for provider in providers or ("primary",):
        if rate_limit_guard:
            stage = rate_limit_state.get(provider)
            plan = rate_limit_guard.worker_plan(provider=provider, stage=stage)
            raw_workers = int(plan["max_workers"])
            capped_workers = min(raw_workers, target_max_workers)
            if capped_workers != raw_workers:
                _append_jsonl(
                    ops_worklog_path,
                    {
                        "timestamp": datetime.now(timezone.utc)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "task": "worker_plan_capped",
                        "provider": provider,
                        "stage": plan["stage"],
                        "raw_max_workers": raw_workers,
                        "max_workers": capped_workers,
                        "target_max_workers": target_max_workers,
                        "catch_up_mode": catch_up_mode,
                        "runbook_ref": runbook_ref,
                    },
                )
            plans.append(
                WorkerPlan(
                    provider=provider,
                    stage=plan["stage"],
                    poll_interval_sec=float(plan["poll_interval_sec"]),
                    max_workers=capped_workers,
                )
            )
        else:
            raw_workers = default_max_workers
            capped_workers = min(raw_workers, target_max_workers)
            if capped_workers != raw_workers:
                _append_jsonl(
                    ops_worklog_path,
                    {
                        "timestamp": datetime.now(timezone.utc)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "task": "worker_plan_capped",
                        "provider": provider,
                        "stage": "stage0",
                        "raw_max_workers": raw_workers,
                        "max_workers": capped_workers,
                        "target_max_workers": target_max_workers,
                        "catch_up_mode": catch_up_mode,
                        "runbook_ref": runbook_ref,
                    },
                )
            plans.append(
                WorkerPlan(
                    provider=provider,
                    stage="stage0",
                    poll_interval_sec=default_poll_interval,
                    max_workers=capped_workers,
                )
            )
    return plans


def run_worker_plan(
    *,
    plan: WorkerPlan,
    task: Callable[[], None] | None = None,
    queue: Iterable[Callable[[], None]] | None = None,
    iterations: int = 1,
    sleep_fn: Callable[[float], None] | None = None,
    stop_when_empty: bool = True,
) -> Mapping[str, Any]:
    """Execute a simple polling loop honoring poll interval and max_workers.

    The loop drains up to ``max_workers`` callables per poll cycle from the
    provided queue. If no queue is provided, the ``task`` is executed
    ``max_workers`` times per iteration to mirror the previous behaviour.
    """

    sleep_fn = sleep_fn or time.sleep
    calls = 0
    polls = 0
    sleeps = 0
    work_queue: deque[Callable[[], None]] = deque(queue or [])
    for _ in range(iterations):
        polls += 1
        executed = 0
        # fire up to max_workers per iteration (synchronously)
        while executed < plan.max_workers:
            if work_queue:
                job = work_queue.popleft()
                job()
                calls += 1
                executed += 1
                continue
            if task is None:
                break
            task()
            calls += 1
            executed += 1
        if stop_when_empty and not work_queue and task is None:
            break
        sleep_fn(plan.poll_interval_sec)
        sleeps += 1
    return {
        "provider": plan.provider,
        "stage": plan.stage,
        "calls": calls,
        "polls": polls,
        "sleep_calls": sleeps,
        "poll_interval_sec": plan.poll_interval_sec,
    }


def run_fetch_workers(
    *,
    plans: Sequence[WorkerPlan],
    queue: Iterable[tuple[str, Callable[[], None]]] | None = None,
    iterations: int = 1,
    sleep_fn: Callable[[float], None] | None = None,
    stop_when_empty: bool = True,
) -> list[Mapping[str, Any]]:
    """Apply worker plans to a provider-keyed queue.

    Each plan drains only jobs matching its provider while honouring
    ``max_workers`` and ``poll_interval_sec``. Queue entries are left
    untouched for other plans so multi-provider scenarios can be tested.
    """

    provider_queues: dict[str, deque[Callable[[], None]]] = {}
    for provider, job in queue or ():
        provider_queues.setdefault(provider, deque()).append(job)

    results: list[Mapping[str, Any]] = []
    for plan in plans:
        provider_queue = provider_queues.get(plan.provider, deque())
        result = run_worker_plan(
            plan=plan,
            task=None,
            queue=provider_queue,
            iterations=iterations,
            sleep_fn=sleep_fn,
            stop_when_empty=stop_when_empty,
        )
        results.append(result)
    return results


def drain_buffers(*, force: bool = False) -> dict[str, int]:
    """Flush in-flight buffers and return statistics for observability."""

    try:
        return DEFAULT_BUFFER_COORDINATOR.drain(force=force)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("data.buffer.drain_failed", extra={"error": str(exc)})
        raise BufferDrainError("buffer drain failed") from exc
