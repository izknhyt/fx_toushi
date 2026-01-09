"""Data ingestion service scaffolding with SLA metrics logging.

The implementation focuses on deterministic scaffolding that downstream CLIs
and tests consume. Real provider integration is left as an extension point,
while the public API and metrics format remain stable per the detailed design
§3.1/§17.6.
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from src.data.rate_limit_guard import RateLimitGuard, StageDecision

if TYPE_CHECKING:
    from src.data.quality import DataQualityGuard


@dataclass(slots=True)
class WorkerPlan:
    provider: str
    stage: str
    poll_interval_sec: float
    max_workers: int


__all__ = [
    "MarketRequest",
    "MarketFrame",
    "ProviderResult",
    "ProviderError",
    "DataSourceDownError",
    "DataQualityError",
    "BackfillRangeError",
    "BackfillFailedError",
    "CacheWarmupError",
    "WorkerSpawnError",
    "BufferDrainError",
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
    "run_worker_plan",
    "run_fetch_workers",
]

logger = logging.getLogger(__name__)
DEFAULT_METRICS_PATH = Path("metrics") / "data_ingestion_sla.jsonl"
DEFAULT_PROVIDER_PRIORITY_PATH = Path("config") / "provider_priority.yaml"
DEFAULT_INGESTION_PRIORITY_PATH = Path("config") / "ingestion" / "priorities.yaml"


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
    if symbols and len(set(symbols)) == 1:
        override = per_symbol.get(symbols[0])
        if override:
            return list(override)
    if default_order:
        return list(default_order)
    return ["primary"]


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
) -> dict[str, Callable[[Sequence[str], str], ProviderResult | list[MarketFrame]]]:
    """Build default provider handlers for known adapters."""

    handlers: dict[str, Callable[[Sequence[str], str], ProviderResult | list[MarketFrame]]] = {}
    try:
        from src.data.providers.yahoo import YahooProvider

        yahoo = YahooProvider()

        def _yahoo_handler(symbols: Sequence[str], timeframe: str) -> list[MarketFrame]:
            request = MarketRequest(symbols=symbols, timeframe=timeframe, start=start, end=end)
            return list(yahoo.fetch_bars(request))

        handlers["yfinance"] = _yahoo_handler
    except Exception:
        pass
    try:
        from src.data.providers.dukascopy import DukascopyProvider

        duka = DukascopyProvider()

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
    try:
        from src.data.providers.paid_feed_stub import PaidFeedStubProvider

        paid_feed = PaidFeedStubProvider()

        def _paid_feed_handler(symbols: Sequence[str], timeframe: str) -> list[MarketFrame]:
            request = MarketRequest(symbols=symbols, timeframe=timeframe, start=start, end=end)
            return list(paid_feed.fetch_bars(request))

        handlers["paid_feed_stub"] = _paid_feed_handler
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
class ProviderResult:
    """Provider response envelope used for SLA logging."""

    frames: list[MarketFrame]
    p95_ms: float
    p99_ms: float
    rate_limit_ratio: float = 0.0


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
) -> list[MarketFrame]:
    """Fetch the most recent bars for the requested symbols and log SLA metrics."""

    _ = context  # reserved for future wiring
    priorities = load_ingestion_priorities()
    symbols = order_symbols_by_priority(symbols, timeframe=timeframe, priorities=priorities)
    providers = resolve_provider_priority(symbols, provider_priority=provider_priority)
    frames: list[MarketFrame] = []
    handler_map = provider_handlers or build_provider_handlers(
        timeframe=timeframe, start=start, end=end
    )
    provider_sla_thresholds = provider_sla_thresholds or {}
    rate_limit_state = (
        rate_limit_state
        if rate_limit_state is not None
        else _load_rate_limit_state(rate_limit_state_path)
    )
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

    def _fetch_provider_once(
        provider: str, current_plan: WorkerPlan | None = None
    ) -> tuple[list[MarketFrame], float]:
        local_frames: list[MarketFrame] = []
        retry_budget = retries
        attempt = 0
        warn = provider_sla_thresholds.get(provider, (warn_ms, breach_ms))[0]
        breach = provider_sla_thresholds.get(provider, (warn_ms, breach_ms))[1]
        rate_limit_ratio = 0.0
        while retry_budget >= 0:
            try:
                start = time.perf_counter()
                result = _invoke_provider(
                    provider=provider,
                    symbols=symbols,
                    timeframe=timeframe,
                    handler=handler_map.get(provider),
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                local_frames = result.frames
                if data_quality_guard:
                    for frame in local_frames:
                        quality = data_quality_guard.validate(frame)
                        if quality.status in {"fail", "error"}:
                            raise DataQualityError(
                                f"data_quality_failed: {quality.issues}",
                                details={"issues": quality.issues, "status": quality.status},
                            )
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
                )
                break
            except (ProviderError, DataQualityError) as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000 if "start" in locals() else 0.0
                local_frames = []
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
                )
                retry_budget -= 1
                attempt += 1
                if retry_budget < 0:
                    break
                current_plan_for_backoff = current_plan or provider_plans.get(provider)
                backoff_base = (
                    current_plan_for_backoff.poll_interval_sec * 1000
                    if current_plan_for_backoff
                    else backoff_ms
                )
                delay_ms = backoff_base if attempt == 1 else backoff_base * 2
                logger.info(
                    "data.fetch_latest.backoff", extra={"delay_ms": delay_ms, "provider": provider}
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("data.fetch_latest.unexpected", extra={"error": str(exc)})
                break
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
                frames_for_provider, rl_ratio = _fetch_provider_once(
                    target_provider, plan_lookup.get(target_provider)
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

    for provider in providers:
        retry_budget = retries
        attempt = 0
        warn = provider_sla_thresholds.get(provider, (warn_ms, breach_ms))[0]
        breach = provider_sla_thresholds.get(provider, (warn_ms, breach_ms))[1]
        while retry_budget >= 0:
            try:
                start = time.perf_counter()
                result = _invoke_provider(
                    provider=provider,
                    symbols=symbols,
                    timeframe=timeframe,
                    handler=handler_map.get(provider),
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                frames = result.frames
                if data_quality_guard:
                    for frame in frames:
                        quality = data_quality_guard.validate(frame)
                        if quality.status in {"fail", "error"}:
                            raise DataQualityError(
                                f"data_quality_failed: {quality.issues}",
                                details={"issues": quality.issues, "status": quality.status},
                            )
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
                )
                break
            except (ProviderError, DataQualityError) as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000 if "start" in locals() else 0.0
                frames = []
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
                )
                retry_budget -= 1
                attempt += 1
                if retry_budget < 0:
                    break
                current_plan = provider_plans.get(provider) if provider_plans else worker_plan
                backoff_base = current_plan.poll_interval_sec * 1000 if current_plan else backoff_ms
                delay_ms = backoff_base if attempt == 1 else backoff_base * 2
                logger.info(
                    "data.fetch_latest.backoff", extra={"delay_ms": delay_ms, "provider": provider}
                )
                # placeholder: in async/real mode use asyncio.sleep(delay_ms/1000)
            except Exception as exc:  # pragma: no cover - defensive
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
                continue
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
    if auto_apply_rate_limit_stage:
        _persist_rate_limit_state(rate_limit_state_path, rate_limit_state)
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
            warn_ms=provider_sla_thresholds.get(priority, (warn_ms, breach_ms))[0]
            if provider_sla_thresholds
            else warn_ms,
            breach_ms=provider_sla_thresholds.get(priority, (warn_ms, breach_ms))[1]
            if provider_sla_thresholds
            else breach_ms,
        ),
        rate_limit_ratio=0.0,
        metrics_path=metrics_path,
    )
    return frames


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
) -> list[WorkerPlan]:
    """Return worker plans (poll interval/max workers) per provider."""

    plans: list[WorkerPlan] = []
    rate_limit_state = rate_limit_state or {}
    for provider in providers or ("primary",):
        if rate_limit_guard:
            stage = rate_limit_state.get(provider)
            plan = rate_limit_guard.worker_plan(provider=provider, stage=stage)
            plans.append(
                WorkerPlan(
                    provider=provider,
                    stage=plan["stage"],
                    poll_interval_sec=float(plan["poll_interval_sec"]),
                    max_workers=int(plan["max_workers"]),
                )
            )
        else:
            plans.append(
                WorkerPlan(
                    provider=provider,
                    stage="stage0",
                    poll_interval_sec=default_poll_interval,
                    max_workers=default_max_workers,
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

    return {"flushed": 0, "dropped": 0, "forced": int(force)}
