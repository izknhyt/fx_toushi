"""Real-time feed evaluation utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

import yaml

DEFAULT_CANDIDATES_PATH = Path("config/providers/real_time_candidates.yaml")
DEFAULT_METRICS_DIR = Path("metrics")


class ProviderProfileError(RuntimeError):
    """Raised when the provider profile is invalid."""


class FeedEvaluationError(RuntimeError):
    """Raised when a feed evaluation fails."""


class FeedLicensingError(RuntimeError):
    """Raised when licensing prerequisites are missing."""


class FeedCostOverflow(RuntimeError):
    """Raised when cost exceeds configured threshold."""


class FeedComparisonError(RuntimeError):
    """Raised when baseline comparison fails."""


@dataclass(slots=True)
class ProviderCandidate:
    provider_id: str
    display_name: str | None
    license_required: bool
    cost_per_hour_jpy: float | None
    rate_limit_per_min: int | None
    max_symbols: int | None
    legal_notes: str | None
    mode: str | None


class ProviderCapabilityRegistry:
    """Loads candidate provider metadata for evaluation."""

    def __init__(self, *, path: Path = DEFAULT_CANDIDATES_PATH) -> None:
        self._path = path
        self._cache: dict[str, ProviderCandidate] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._cache = {}
            return
        payload = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise ProviderProfileError("real_time_candidates schema invalid")
        candidates = payload.get("candidates", [])
        if not isinstance(candidates, list):
            raise ProviderProfileError("real_time_candidates.candidates must be list")
        cache: dict[str, ProviderCandidate] = {}
        for entry in candidates:
            if not isinstance(entry, Mapping):
                continue
            provider_id = str(entry.get("provider_id") or entry.get("id") or "")
            if not provider_id:
                continue
            cache[provider_id] = ProviderCandidate(
                provider_id=provider_id,
                display_name=entry.get("display_name"),
                license_required=bool(entry.get("license_required", True)),
                cost_per_hour_jpy=_optional_float(entry.get("cost_per_hour_jpy")),
                rate_limit_per_min=_optional_int(entry.get("rate_limit_per_min")),
                max_symbols=_optional_int(entry.get("max_symbols")),
                legal_notes=entry.get("legal_notes"),
                mode=entry.get("mode"),
            )
        self._cache = cache

    def get(self, provider_id: str) -> ProviderCandidate | None:
        return self._cache.get(provider_id)

    def require(self, provider_id: str) -> ProviderCandidate:
        candidate = self.get(provider_id)
        if not candidate:
            raise ProviderProfileError(f"unknown provider: {provider_id}")
        return candidate


@dataclass(slots=True)
class FeedEvaluationConfig:
    max_fetch_p95_ms: float = 12_000.0
    max_hourly_cost_jpy: float = 10_000.0
    min_uptime_pct: float = 99.0


@dataclass(slots=True)
class FeedEvaluationResult:
    provider_id: str
    window_hours: float
    fetch_p95_ms: float
    fetch_p99_ms: float
    processing_p95_ms: float
    uptime_pct: float
    rate_limit_hits: int
    cost_per_hour_jpy: float
    comparison_gap_p95_pips: float
    decision: str
    notes: str | None
    ts: str

    def to_dict(self) -> dict[str, object]:
        return {
            "ts": self.ts,
            "provider_id": self.provider_id,
            "window_hours": self.window_hours,
            "fetch_p95_ms": self.fetch_p95_ms,
            "fetch_p99_ms": self.fetch_p99_ms,
            "processing_p95_ms": self.processing_p95_ms,
            "uptime_pct": self.uptime_pct,
            "rate_limit_hits": self.rate_limit_hits,
            "cost_per_hour_jpy": self.cost_per_hour_jpy,
            "comparison_gap_p95_pips": self.comparison_gap_p95_pips,
            "decision": self.decision,
            "notes": self.notes,
        }


@dataclass(slots=True)
class ShadowComparisonReport:
    provider_id: str
    primary_provider: str
    window_hours: float
    gap_p95_pips: float
    missing_pct: float

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "primary_provider": self.primary_provider,
            "window_hours": self.window_hours,
            "gap_p95_pips": self.gap_p95_pips,
            "missing_pct": self.missing_pct,
        }


@dataclass(slots=True)
class ThresholdProposal:
    provider_id: str
    max_fetch_p95_ms: float
    max_fetch_p99_ms: float
    min_uptime_pct: float
    max_rate_limit_hits: int
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "max_fetch_p95_ms": self.max_fetch_p95_ms,
            "max_fetch_p99_ms": self.max_fetch_p99_ms,
            "min_uptime_pct": self.min_uptime_pct,
            "max_rate_limit_hits": self.max_rate_limit_hits,
            "notes": self.notes,
        }


class RealTimeFeedEvaluator:
    """Evaluate candidate real-time feeds against baseline metrics."""

    def __init__(
        self,
        *,
        registry: ProviderCapabilityRegistry | None = None,
        metrics_dir: Path = DEFAULT_METRICS_DIR,
        config: FeedEvaluationConfig | None = None,
        license_registry: object | None = None,
    ) -> None:
        self._registry = registry or ProviderCapabilityRegistry()
        self._metrics_dir = metrics_dir
        self._config = config or FeedEvaluationConfig()
        self._license_registry = license_registry

    def run(
        self,
        *,
        provider_id: str,
        window_hours: float,
        fetch_samples_ms: Iterable[float],
        processing_samples_ms: Iterable[float],
        comparison_gap_pips: Iterable[float] | None = None,
        rate_limit_hits: int = 0,
        uptime_pct: float | None = None,
        cost_per_hour_jpy: float | None = None,
        license_ok: bool = True,
        notes: str | None = None,
    ) -> FeedEvaluationResult:
        candidate = self._registry.require(provider_id)
        if candidate.license_required and not license_ok:
            raise FeedLicensingError(f"license missing for {provider_id}")
        if candidate.license_required and self._license_registry is not None:
            try:
                self._license_registry.ensure_precheck(provider_id)
            except Exception as exc:  # noqa: BLE001
                raise FeedLicensingError(str(exc)) from exc
        fetch_samples = list(fetch_samples_ms)
        processing_samples = list(processing_samples_ms)
        if not fetch_samples or not processing_samples:
            raise FeedEvaluationError("missing latency samples")
        fetch_p95 = _percentile(fetch_samples, 95)
        fetch_p99 = _percentile(fetch_samples, 99)
        processing_p95 = _percentile(processing_samples, 95)
        uptime = uptime_pct if uptime_pct is not None else 100.0
        gap_samples = list(comparison_gap_pips or [])
        comparison_gap = _percentile(gap_samples, 95) if gap_samples else 0.0
        cost_per_hour = (
            cost_per_hour_jpy
            if cost_per_hour_jpy is not None
            else float(candidate.cost_per_hour_jpy or 0.0)
        )
        if cost_per_hour > self._config.max_hourly_cost_jpy:
            raise FeedCostOverflow(f"cost_per_hour_jpy {cost_per_hour} exceeds limit")
        decision = _decision_from_metrics(
            fetch_p95=fetch_p95,
            uptime_pct=uptime,
            cost_per_hour=cost_per_hour,
            config=self._config,
        )
        result = FeedEvaluationResult(
            provider_id=provider_id,
            window_hours=window_hours,
            fetch_p95_ms=fetch_p95,
            fetch_p99_ms=fetch_p99,
            processing_p95_ms=processing_p95,
            uptime_pct=uptime,
            rate_limit_hits=rate_limit_hits,
            cost_per_hour_jpy=cost_per_hour,
            comparison_gap_p95_pips=comparison_gap,
            decision=decision,
            notes=notes,
            ts=_utcnow_iso(),
        )
        self._append_metrics(provider_id, result.to_dict())
        _maybe_alert(result, self._config)
        return result

    def shadow_compare(
        self,
        *,
        provider_id: str,
        primary_provider: str,
        window_hours: float,
        comparison_gap_pips: Iterable[float],
        missing_pct: float,
    ) -> ShadowComparisonReport:
        self._registry.require(provider_id)
        if missing_pct < 0.0 or missing_pct > 100.0:
            raise FeedComparisonError("missing_pct must be 0-100")
        gaps = list(comparison_gap_pips)
        if not gaps:
            raise FeedComparisonError("comparison gaps required")
        gap_p95 = _percentile(gaps, 95)
        return ShadowComparisonReport(
            provider_id=provider_id,
            primary_provider=primary_provider,
            window_hours=window_hours,
            gap_p95_pips=gap_p95,
            missing_pct=missing_pct,
        )

    def apply_thresholds(self, result: FeedEvaluationResult) -> ThresholdProposal:
        max_fetch_p99 = max(result.fetch_p99_ms, result.fetch_p95_ms) * 1.2
        return ThresholdProposal(
            provider_id=result.provider_id,
            max_fetch_p95_ms=max(result.fetch_p95_ms, self._config.max_fetch_p95_ms),
            max_fetch_p99_ms=max_fetch_p99,
            min_uptime_pct=min(result.uptime_pct, 100.0),
            max_rate_limit_hits=max(result.rate_limit_hits, 1),
            notes="auto-generated from feed evaluation",
        )

    def _append_metrics(self, provider_id: str, payload: Mapping[str, object]) -> None:
        self._metrics_dir.mkdir(parents=True, exist_ok=True)
        path = self._metrics_dir / f"feed_evaluation_{provider_id}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _decision_from_metrics(
    *, fetch_p95: float, uptime_pct: float, cost_per_hour: float, config: FeedEvaluationConfig
) -> str:
    if fetch_p95 > config.max_fetch_p95_ms or uptime_pct < config.min_uptime_pct:
        return "hold"
    if cost_per_hour > config.max_hourly_cost_jpy:
        return "reject"
    return "candidate"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise FeedEvaluationError("percentile input empty")
    if percentile <= 0:
        return min(values)
    if percentile >= 100:
        return max(values)
    ordered = sorted(values)
    rank = (percentile / 100) * (len(ordered) - 1)
    lower = ordered[int(rank)]
    upper = ordered[min(int(rank) + 1, len(ordered) - 1)]
    weight = rank - int(rank)
    return lower + (upper - lower) * weight


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _maybe_alert(result: FeedEvaluationResult, config: FeedEvaluationConfig) -> None:
    if result.fetch_p95_ms <= config.max_fetch_p95_ms and result.cost_per_hour_jpy <= config.max_hourly_cost_jpy:
        return
    try:
        from src.infra.alert import AlertDispatcher
    except Exception:
        return
    dispatcher = AlertDispatcher()
    messages = []
    if result.fetch_p95_ms > config.max_fetch_p95_ms:
        messages.append(f"fetch_p95_ms {result.fetch_p95_ms} exceeds {config.max_fetch_p95_ms}")
    if result.cost_per_hour_jpy > config.max_hourly_cost_jpy:
        messages.append(
            f"cost_per_hour_jpy {result.cost_per_hour_jpy} exceeds {config.max_hourly_cost_jpy}"
        )
    dispatcher.dispatch(level="warning", message=f"[feed_eval] {result.provider_id}: " + "; ".join(messages))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "ProviderCapabilityRegistry",
    "ProviderCandidate",
    "RealTimeFeedEvaluator",
    "FeedEvaluationConfig",
    "FeedEvaluationResult",
    "ShadowComparisonReport",
    "ThresholdProposal",
    "ProviderProfileError",
    "FeedEvaluationError",
    "FeedLicensingError",
    "FeedCostOverflow",
    "FeedComparisonError",
]
