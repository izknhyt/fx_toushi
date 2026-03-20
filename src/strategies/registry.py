"""Strategy registry and manifest validation utilities.

This module wires the :mod:`src.strategies.base` plugin contracts into a
light-weight ``StrategyEngine`` that can register strategy plugins, load a
manifest file, and execute the enabled strategies with a deterministic
``StrategyContext`` snapshot.  The implementation intentionally focuses on
the coordination and validation logic that the surrounding tests exercise;
future implementation packets can extend the error handling and
instrumentation without breaking the public API introduced here.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Iterable, Iterator, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from src.features.pipeline import FeatureContext, FeaturePipeline
from src.strategies.allocation import (
    AllocationActivePosition,
    AllocationCandidate,
    AllocationContext,
    AllocationOutcome,
    StrategyAllocationPolicy,
)
from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol
from src.strategies.candidate import CandidateTrade

__all__ = [
    "ManifestLoadError",
    "ManifestValidationError",
    "StrategyExecutionError",
    "StrategyRegistryError",
    "StrategyRegistrationError",
    "StrategyManifest",
    "StrategyEngine",
    "compute_deterministic_hash",
]

logger = logging.getLogger(__name__)
DEFAULT_SIGNAL_EVENT_LOG = Path("logs") / "events" / "signal.generated.jsonl"
DEFAULT_DETERMINISM_METRICS = Path("metrics") / "determinism.jsonl"
DEFAULT_LOG_MAX_BYTES = 64 * 1024 * 1024
DEFAULT_LOG_KEEP_BYTES = 8 * 1024 * 1024


def _as_utc(value: datetime | None) -> datetime:
    """Return a timezone-aware UTC datetime for lifecycle comparisons."""

    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalise_symbol_set(symbols: Iterable[str]) -> frozenset[str]:
    """Normalise symbol identifiers to uppercase for watchlist comparisons."""

    normalised: set[str] = set()
    for symbol in symbols:
        token = str(symbol).strip()
        if not token:
            continue
        normalised.add(token.upper())
    return frozenset(normalised)


def _tail_bytes(path: Path, keep_bytes: int) -> bytes:
    if keep_bytes <= 0:
        return b""
    size = path.stat().st_size
    if size <= keep_bytes:
        return path.read_bytes()
    with path.open("rb") as handle:
        handle.seek(size - keep_bytes)
        tail = handle.read()
    first_newline = tail.find(b"\n")
    if first_newline >= 0:
        return tail[first_newline + 1 :]
    return tail


def _maybe_rotate_log(path: Path, *, max_bytes: int | None, keep_bytes: int) -> None:
    if max_bytes is None or max_bytes <= 0 or not path.exists():
        return
    if path.stat().st_size <= max_bytes:
        return
    tail = _tail_bytes(path, keep_bytes)
    with path.open("wb") as handle:
        handle.write(tail)


def _append_jsonl(
    path: Path,
    payload: Mapping[str, Any],
    *,
    max_bytes: int | None = None,
    keep_bytes: int = DEFAULT_LOG_KEEP_BYTES,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _maybe_rotate_log(path, max_bytes=max_bytes, keep_bytes=keep_bytes)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _int_env(name: str, default: int | None) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value <= 0:
        return None
    return value


def _is_guarded_mode(gate: Any) -> bool:
    risk = getattr(gate, "risk", None)
    if risk is not None and bool(getattr(risk, "reduce_only", False)):
        return True
    market = getattr(gate, "market", None)
    if market is not None:
        status = getattr(market, "profit_readiness_status", None)
        if isinstance(status, str) and status.lower() in {"guarded", "halted"}:
            return True
    return False


def _utcnow_iso() -> str:
    """Return a compact UTC timestamp for logging."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    getter = getattr(value, "iloc", None)
    if getter is not None:
        try:
            return float(value.iloc[-1])
        except Exception:
            return None
    try:
        return float(value)
    except Exception:
        return None


def _extract_map(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _timeframe_to_minutes(value: str | None) -> int:
    token = (value or "5m").strip().lower()
    if token.endswith("m"):
        try:
            return max(1, int(token[:-1]))
        except ValueError:
            return 5
    if token.endswith("h"):
        try:
            return max(1, int(token[:-1])) * 60
        except ValueError:
            return 60
    if token.endswith("d"):
        try:
            return max(1, int(token[:-1])) * 1440
        except ValueError:
            return 1440
    return 5


def _latest_feature(
    *,
    context: Any,
    symbol: str,
    feature: str,
    timeframe: str,
) -> float | None:
    features = getattr(context, "features", None)
    if features is None:
        return None
    try:
        value = features.lookup(symbol=symbol, feature=feature, timeframe=timeframe)
    except Exception:
        return None
    return _coerce_float(value)


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat().replace("+00:00", "Z")
    return None


def _candidate_id_from_parts(*parts: Any) -> str:
    payload = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _derive_signal_trade_fields(*, signal: Any, context: Any) -> dict[str, Any]:
    symbol_raw = getattr(signal, "symbol", None)
    symbol = str(symbol_raw).upper() if isinstance(symbol_raw, str) and symbol_raw.strip() else None
    direction_raw = getattr(signal, "direction", None)
    direction = str(direction_raw).lower() if isinstance(direction_raw, str) else None

    params = _extract_map(getattr(context, "parameters", {}))
    entry_cfg = _extract_map(params.get("entry"))
    sizing_cfg = _extract_map(params.get("sizing"))
    execution_cfg = _extract_map(params.get("execution"))

    level = _coerce_float(getattr(signal, "level", None))
    buffer = _coerce_float(getattr(signal, "buffer", None))
    entry = _coerce_float(getattr(signal, "entry", None))
    stop = _coerce_float(getattr(signal, "stop", None))
    target = _coerce_float(getattr(signal, "target", None))
    expire_at = _iso_or_none(getattr(signal, "expire_at", None))

    ttl_bars = int(sizing_cfg.get("ttl_bars") or getattr(signal, "ttl_bars", None) or 0)
    if ttl_bars <= 0:
        ttl_bars = 1
    entry_minutes = int(
        getattr(signal, "entry_timeframe_minutes", None)
        or _timeframe_to_minutes(str(entry_cfg.get("timeframe", "5m")))
    )
    entry_minutes = max(1, entry_minutes)
    target_r_multiple = _coerce_float(
        getattr(signal, "target_r_multiple", None)
    ) or _coerce_float(sizing_cfg.get("tp_r_multiple")) or 1.0
    atr_sl_mult = _coerce_float(sizing_cfg.get("atr_sl_mult")) or 1.0
    spread_pips = _coerce_float(
        getattr(signal, "spread_pips", None)
    ) or _coerce_float(execution_cfg.get("spread")) or 0.0
    slippage_pips = _coerce_float(
        getattr(signal, "slippage_pips", None)
    ) or _coerce_float(execution_cfg.get("slippage")) or 0.0
    slippage_std = _coerce_float(
        getattr(signal, "slippage_std", None)
    ) or _coerce_float(execution_cfg.get("slippage_std")) or 0.0
    trail_atr_mult = _coerce_float(
        getattr(signal, "trail_atr_mult", None)
    ) or _coerce_float(sizing_cfg.get("atr_sl_mult"))

    close_price = _coerce_float(getattr(signal, "price", None))
    atr_value = None
    if symbol is not None:
        close_price = close_price or _latest_feature(
            context=context,
            symbol=symbol,
            feature="close_5m",
            timeframe="5m",
        )
        atr_value = _latest_feature(
            context=context,
            symbol=symbol,
            feature="atr_14_1h",
            timeframe="1h",
        )
    atr_value = atr_value or 0.08

    if entry is None and close_price is not None and direction in {"long", "short"}:
        if direction == "long":
            entry = close_price + spread_pips + slippage_pips
        else:
            entry = close_price - spread_pips - slippage_pips

    risk_distance = None
    if entry is not None and stop is not None:
        risk_distance = abs(entry - stop)
    if risk_distance is None and close_price is not None:
        raw = max(atr_value * max(0.1, atr_sl_mult), 0.0)
        min_distance = max(close_price * 0.0002, 0.0005)
        max_distance = max(close_price * 0.02, min_distance)
        risk_distance = min(max(raw, min_distance), max_distance)

    if stop is None and entry is not None and risk_distance is not None and direction in {"long", "short"}:
        if direction == "long":
            stop = entry - risk_distance
        else:
            stop = entry + risk_distance
    if target is None and entry is not None and risk_distance is not None and direction in {"long", "short"}:
        if direction == "long":
            target = entry + target_r_multiple * risk_distance
        else:
            target = entry - target_r_multiple * risk_distance
    if level is None and entry is not None:
        level = entry
    if buffer is None and risk_distance is not None:
        buffer = risk_distance
    if expire_at is None:
        now = getattr(getattr(context, "clock", None), "now", None)
        if isinstance(now, datetime):
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            else:
                now = now.astimezone(timezone.utc)
            expire_at = (now + timedelta(minutes=entry_minutes * ttl_bars)).isoformat().replace(
                "+00:00", "Z"
            )

    return {
        "entry": entry,
        "stop": stop,
        "target": target,
        "level": level,
        "buffer": buffer,
        "expire_at": expire_at,
        "ttl_bars": ttl_bars,
        "entry_timeframe_minutes": entry_minutes,
        "target_r_multiple": target_r_multiple,
        "trail_atr_mult": trail_atr_mult,
        "spread_pips": spread_pips,
        "slippage_pips": slippage_pips,
        "slippage_std": slippage_std,
        "atr_value": atr_value,
    }


def compute_deterministic_hash(
    *,
    strategy_id: str,
    determinism_key: str,
    seed: int,
    watchlist: Iterable[str],
    required_features: Iterable[str],
    feature_version: str | None = None,
    data_manifest_hash: str | None = None,
    strategy_config: Mapping[str, Any] | None = None,
) -> str:
    """Return a deterministic digest summarising a strategy evaluation."""

    payload = {
        "strategy_id": strategy_id,
        "determinism_key": determinism_key.strip(),
        "seed": seed,
        "watchlist": sorted(watchlist),
        "required_features": sorted(required_features),
    }
    if feature_version:
        payload["feature_version"] = feature_version
    if data_manifest_hash:
        payload["data_manifest_hash"] = data_manifest_hash
    if strategy_config:
        payload["strategy_config"] = strategy_config
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.blake2b(serialized, digest_size=16).hexdigest()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class StrategyRegistryError(RuntimeError):
    """Base class for strategy registry errors."""


class StrategyRegistrationError(StrategyRegistryError):
    """Raised when registering a plugin fails validation."""


class ManifestLoadError(StrategyRegistryError):
    """Raised when a manifest file cannot be loaded from disk."""


class ManifestValidationError(StrategyRegistryError):
    """Raised when a manifest fails schema or contract validation."""

    def __init__(self, message: str, *, errors: Sequence[Any] | None = None) -> None:
        super().__init__(message)
        self.errors: tuple[Any, ...] = tuple(errors or ())


class StrategyExecutionError(StrategyRegistryError):
    """Raised when a strategy plugin fails during evaluation."""

    def __init__(self, strategy_id: str, cause: BaseException) -> None:
        self.strategy_id = strategy_id
        self.cause = cause
        message = f"Strategy '{strategy_id}' execution failed: {cause!r}"
        super().__init__(message)


# ---------------------------------------------------------------------------
# Manifest models
# ---------------------------------------------------------------------------


class DatasetReference(BaseModel):
    """Dataset dependency surfaced in the strategy manifest."""

    id: str
    version: str
    validation_playbook_id: str


class GovernanceRecord(BaseModel):
    """Governance metadata recorded for a strategy entry."""

    ticket_id: str
    last_board_decision: datetime
    reviewers: tuple[str, ...]


class StrategyLifecycle(BaseModel):
    """Lifecycle metadata enforcing validation cadences and statuses."""

    status: Literal["draft", "active", "deprecated", "blocked"] = "draft"
    last_validated_at: datetime
    expires_at: datetime | None = None
    deprecated_after_days: int = Field(default=90, ge=7, le=365)
    runbook_ref: str | None = None

    @model_validator(mode="after")
    def _normalise_timestamps(self) -> StrategyLifecycle:
        self.last_validated_at = _as_utc(self.last_validated_at)
        if self.expires_at is not None:
            self.expires_at = _as_utc(self.expires_at)
        return self

    def effective_status(
        self, *, now: datetime | None = None
    ) -> Literal["draft", "active", "deprecated", "blocked"]:
        """Return the effective status considering expiry/validation age."""

        reference = _as_utc(now)
        if self.status == "blocked":
            return "blocked"
        if self.status == "deprecated":
            return "deprecated"

        if self.expires_at and reference >= self.expires_at:
            return "deprecated"

        if reference - self.last_validated_at > timedelta(days=self.deprecated_after_days):
            return "deprecated"

        return self.status

    def is_stale(self, *, now: datetime | None = None) -> bool:
        """Return True when the lifecycle would resolve to 'deprecated'."""

        return self.effective_status(now=now) == "deprecated"


class StrategyMetadataModel(BaseModel):
    """Static metadata asserted by the manifest for a strategy plugin."""

    name: str
    version: str
    required_features: tuple[str, ...]
    tags: tuple[str, ...] = ()
    seed_offset: int = 0

    @field_validator("required_features")
    @classmethod
    def _normalise_required_features(cls, values: Sequence[str]) -> tuple[str, ...]:
        normalised: list[str] = []
        seen: set[str] = set()
        for feature in values:
            candidate = feature.strip()
            if not candidate:
                msg = "required_features entries must be non-empty strings"
                raise ValueError(msg)
            if candidate not in seen:
                normalised.append(candidate)
                seen.add(candidate)
        if not normalised:
            msg = "required_features must contain at least one entry"
            raise ValueError(msg)
        return tuple(normalised)

    def to_runtime(self) -> StrategyMetadata:
        """Convert the model to the runtime :class:`StrategyMetadata`."""

        return StrategyMetadata(
            name=self.name,
            version=self.version,
            required_features=frozenset(self.required_features),
            tags=frozenset(self.tags),
            seed_offset=self.seed_offset,
        )

    @property
    def required_feature_set(self) -> frozenset[str]:
        """Return the required features as a ``frozenset``."""

        return frozenset(self.required_features)


class StrategyEntry(BaseModel):
    """Manifest entry describing a single strategy plugin."""

    enabled: bool = True
    priority: int = Field(ge=0, le=255)
    weight: float = Field(ge=0.0, le=1.0)
    metadata: StrategyMetadataModel
    feature_flags: Mapping[str, bool] = Field(default_factory=dict)
    datasets: tuple[DatasetReference, ...] = ()
    governance: GovernanceRecord | None = None
    watchlist: tuple[str, ...] | None = None
    lifecycle: StrategyLifecycle | None = None
    parameters: Mapping[str, Any] = Field(default_factory=dict)
    determinism_key: str

    @field_validator("feature_flags")
    @classmethod
    def _normalise_feature_flags(cls, value: Mapping[str, Any]) -> Mapping[str, bool]:
        normalised: dict[str, bool] = {}
        for key, flag in value.items():
            normalised[str(key)] = bool(flag)
        return normalised

    @field_validator("watchlist")
    @classmethod
    def _normalise_watchlist(cls, value: Sequence[str] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        normalised: list[str] = []
        seen: set[str] = set()
        for symbol in value:
            token = str(symbol).strip().upper()
            if not token:
                raise ValueError("Watchlist symbols must be non-empty strings")
            if token not in seen:
                normalised.append(token)
                seen.add(token)
        return tuple(normalised) if normalised else None

    @field_validator("determinism_key")
    @classmethod
    def _validate_determinism_key(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("determinism_key must be a non-empty string")
        return token

    @property
    def enabled_feature_flags(self) -> frozenset[str]:
        """Return the subset of feature flags that are enabled."""

        return frozenset(key for key, enabled in self.feature_flags.items() if bool(enabled))

    def effective_status(
        self, *, now: datetime | None = None
    ) -> Literal["draft", "active", "deprecated", "blocked"]:
        """Return the lifecycle status resolved against validation cadence."""

        if self.lifecycle is None:
            return "active" if self.enabled else "draft"
        return self.lifecycle.effective_status(now=now)


class StrategyManifest(BaseModel):
    """Pydantic model describing the structure of ``strategy_manifest.yaml``."""

    schema_version: int | str
    manifest_name: str
    revision_tag: str
    last_reviewed_at: datetime
    notes: str | None = None
    strategies: MutableMapping[str, StrategyEntry]

    @field_validator("strategies")
    @classmethod
    def _ensure_strategies(
        cls, value: Mapping[str, StrategyEntry]
    ) -> MutableMapping[str, StrategyEntry]:
        if not value:
            msg = "Manifest must declare at least one strategy entry"
            raise ValueError(msg)
        normalised: dict[str, StrategyEntry] = {}
        for key, entry in value.items():
            strategy_id = str(key).strip()
            if not strategy_id:
                msg = "Strategy identifiers must be non-empty strings"
                raise ValueError(msg)
            normalised[strategy_id] = entry
        return normalised

    @model_validator(mode="after")
    def _validate_weights(self) -> StrategyManifest:
        total_weight = sum(entry.weight for entry in self.strategies.values() if entry.enabled)
        if total_weight > 1.0 + 1e-9:
            msg = "Sum of enabled strategy weights must not exceed 1.0"
            raise ValueError(msg)
        return self

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> StrategyManifest:
        """Validate and construct a manifest from an in-memory mapping."""

        try:
            return cls.model_validate(payload)
        except ValidationError as exc:  # pragma: no cover - defensive
            raise ManifestValidationError(
                "Strategy manifest validation failed", errors=exc.errors()
            ) from exc

    @classmethod
    def load(cls, path: str | Path) -> StrategyManifest:
        """Load a manifest from a YAML file and validate the payload."""

        manifest_path = Path(path)
        if not manifest_path.exists():
            msg = f"Manifest file does not exist: {manifest_path}"
            raise ManifestLoadError(msg)

        with manifest_path.open("r", encoding="utf-8") as handle:
            raw_text = handle.read()
        try:
            payload = yaml.safe_load(raw_text)
        except Exception as exc:  # pragma: no cover - defensive
            raise ManifestLoadError(f"Failed to parse manifest YAML: {exc}") from exc

        manifest = cls.from_dict(payload)
        manifest.validate_lifecycle()
        return manifest

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def enabled_strategies(self) -> Iterator[tuple[str, StrategyEntry]]:
        """Yield ``(strategy_id, entry)`` pairs for enabled strategies."""

        for strategy_id, entry in self.strategies.items():
            if entry.enabled:
                yield strategy_id, entry

    def validate_feature_contract(self, available_features: Iterable[str]) -> None:
        """Ensure all enabled strategies can find their required features."""

        feature_set = frozenset(available_features)
        missing_map: dict[str, frozenset[str]] = {}
        for strategy_id, entry in self.enabled_strategies():
            missing = entry.metadata.required_feature_set - feature_set
            if missing:
                missing_map[strategy_id] = missing
        if missing_map:
            details = {
                strategy_id: sorted(features) for strategy_id, features in missing_map.items()
            }
            msg = "Strategy manifest references unavailable features"
            raise ManifestValidationError(f"{msg}: {details}")

    def validate_watchlists(self, available_symbols: Iterable[str]) -> None:
        """Ensure strategy watchlists only reference available symbols."""

        symbol_set = _normalise_symbol_set(available_symbols)
        violations: dict[str, list[str]] = {}
        for strategy_id, entry in self.enabled_strategies():
            if not entry.watchlist:
                continue
            missing = frozenset(entry.watchlist) - symbol_set
            if missing:
                violations[strategy_id] = sorted(missing)
        if violations:
            msg = "Strategy watchlist references symbols missing from feature context"
            raise ManifestValidationError(f"{msg}: {violations}")

    def resolve_watchlist(
        self,
        available_symbols: Iterable[str],
        *,
        now: datetime | None = None,
    ) -> frozenset[str]:
        """Return the final watchlist derived from manifest entries."""

        symbol_set = _normalise_symbol_set(available_symbols)
        self.validate_watchlists(symbol_set)

        resolved: set[str] = set()
        for _, entry in self.enabled_strategies():
            if entry.effective_status(now=now) == "deprecated":
                continue
            if entry.watchlist:
                resolved.update(frozenset(entry.watchlist) & symbol_set)

        if not resolved:
            resolved.update(symbol_set)

        return frozenset(resolved)

    def validate_lifecycle(self, *, now: datetime | None = None) -> None:
        """Ensure enabled strategies comply with lifecycle requirements."""

        reference = _as_utc(now)
        stale: dict[str, str] = {}
        for strategy_id, entry in self.enabled_strategies():
            status = entry.effective_status(now=reference)
            if status == "deprecated":
                reason = "status=deprecated"
                if entry.lifecycle and entry.lifecycle.is_stale(now=reference):
                    reason = "validation stale (> deprecated_after_days)"
                stale[strategy_id] = reason

        if stale:
            details = ", ".join(f"{strategy_id}: {reason}" for strategy_id, reason in stale.items())
            raise ManifestValidationError(
                f"Enabled strategies have lapsed lifecycle status: {details}"
            )


# ---------------------------------------------------------------------------
# Strategy engine
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class StrategyEvaluationContext:
    """Runtime inputs used to construct :class:`StrategyContext`."""

    features: FeatureContext
    regime: Any
    gate: Any
    account: Any
    config: Any
    clock: Any
    watchlist: Iterable[str]
    seed: int


class StrategyEngine:
    """Simple registry that executes strategy plugins based on a manifest."""

    def __init__(
        self,
        *,
        determinism_log_path: Path | None = None,
        determinism_metrics_path: Path | None = None,
    ) -> None:
        self._plugins: dict[str, StrategyPluginProtocol] = {}
        self._manifest: StrategyManifest | None = None
        self._last_determinism_events: list[Mapping[str, Any]] = []
        self._last_allocation_outcomes: list[Mapping[str, Any]] = []
        self._last_candidate_trades: list[Mapping[str, Any]] = []
        self._determinism_log_path = (
            Path("logs") / "strategy" / "registry.log"
            if determinism_log_path is None
            else Path(determinism_log_path)
        )
        self._determinism_log_max_bytes = _int_env(
            "TRADECTL_STRATEGY_LOG_MAX_BYTES",
            DEFAULT_LOG_MAX_BYTES,
        )
        self._determinism_log_keep_bytes = _int_env(
            "TRADECTL_STRATEGY_LOG_KEEP_BYTES",
            DEFAULT_LOG_KEEP_BYTES,
        ) or DEFAULT_LOG_KEEP_BYTES
        if determinism_metrics_path is not None:
            self._determinism_metrics_path = Path(determinism_metrics_path)
        else:
            env_path = os.getenv("TRADECTL_DETERMINISM_METRICS")
            self._determinism_metrics_path = Path(env_path) if env_path else DEFAULT_DETERMINISM_METRICS
        self._determinism_metrics_max_bytes = _int_env(
            "TRADECTL_DETERMINISM_METRICS_MAX_BYTES",
            DEFAULT_LOG_MAX_BYTES,
        )
        self._determinism_metrics_keep_bytes = _int_env(
            "TRADECTL_DETERMINISM_METRICS_KEEP_BYTES",
            DEFAULT_LOG_KEEP_BYTES,
        ) or DEFAULT_LOG_KEEP_BYTES
        signal_env = os.getenv("TRADECTL_SIGNAL_EVENT_LOG")
        self._signal_log_path = (
            Path(signal_env) if signal_env else DEFAULT_SIGNAL_EVENT_LOG
        )
        self._signal_log_max_bytes = _int_env(
            "TRADECTL_SIGNAL_LOG_MAX_BYTES",
            DEFAULT_LOG_MAX_BYTES,
        )
        self._signal_log_keep_bytes = _int_env(
            "TRADECTL_SIGNAL_LOG_KEEP_BYTES",
            DEFAULT_LOG_KEEP_BYTES,
        ) or DEFAULT_LOG_KEEP_BYTES
        self._allocation_policy: StrategyAllocationPolicy | None = None

    # ------------------------------------------------------------------
    # Plugin registration & manifest loading
    # ------------------------------------------------------------------
    def register_plugin(self, plugin: StrategyPluginProtocol) -> None:
        """Register a strategy plugin with the engine."""

        if not isinstance(plugin, StrategyPluginProtocol):
            msg = f"Plugin '{plugin!r}' does not satisfy StrategyPluginProtocol"
            raise StrategyRegistrationError(msg)

        strategy_id = getattr(plugin, "id", None)
        if not isinstance(strategy_id, str) or not strategy_id:
            msg = "Strategy plugins must define a non-empty 'id' attribute"
            raise StrategyRegistrationError(msg)

        if strategy_id in self._plugins:
            msg = f"Strategy '{strategy_id}' is already registered"
            raise StrategyRegistrationError(msg)

        determinism_key = getattr(plugin, "determinism_key", None)
        if not isinstance(determinism_key, str) or not determinism_key.strip():
            logger.error(
                "strategy.registry.determinism_key_missing",
                extra={"strategy_id": strategy_id},
            )
            msg = f"Strategy '{strategy_id}' must declare a non-empty 'determinism_key'"
            raise StrategyRegistrationError(msg)

        metadata = getattr(plugin, "metadata", None)
        if not isinstance(metadata, StrategyMetadata):
            msg = f"Strategy '{strategy_id}' must expose StrategyMetadata"
            raise StrategyRegistrationError(msg)

        self._plugins[strategy_id] = plugin

    def load_manifest(self, path: str | Path) -> StrategyManifest:
        """Load and store the manifest used for subsequent executions."""

        manifest = StrategyManifest.load(path)
        self._manifest = manifest
        return manifest

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    @property
    def manifest(self) -> StrategyManifest | None:
        """Return the currently loaded manifest (if any)."""

        return self._manifest

    @property
    def registered_strategies(self) -> frozenset[str]:
        """Return the identifiers of registered strategy plugins."""

        return frozenset(self._plugins)

    @property
    def last_run_determinism_events(self) -> tuple[Mapping[str, Any], ...]:
        """Return determinism audit events emitted during the most recent run."""

        return tuple(self._last_determinism_events)

    @property
    def last_run_allocation_outcomes(self) -> tuple[Mapping[str, Any], ...]:
        """Return allocation decision payloads emitted during the most recent run."""

        return tuple(self._last_allocation_outcomes)

    @property
    def last_run_candidate_trades(self) -> tuple[Mapping[str, Any], ...]:
        """Return canonical candidate payloads emitted during the most recent run."""

        return tuple(self._last_candidate_trades)

    @property
    def allocation_policy(self) -> StrategyAllocationPolicy | None:
        """Return the configured allocation policy (if any)."""

        return self._allocation_policy

    def set_allocation_policy(self, policy: StrategyAllocationPolicy | None) -> None:
        """Attach an allocation policy to the engine."""

        self._allocation_policy = policy

    def clear_allocation_policy(self) -> None:
        """Disable the allocation policy and restore pass-through execution."""

        self._allocation_policy = None

    def get_parameters(self, strategy_id: str) -> Mapping[str, Any]:
        """Return manifest parameters for ``strategy_id`` (if available)."""

        if self._manifest is None:
            msg = "Strategy manifest has not been loaded"
            raise ManifestLoadError(msg)

        try:
            entry = self._manifest.strategies[strategy_id]
        except KeyError as exc:  # pragma: no cover - defensive
            raise StrategyRegistrationError(
                f"Strategy '{strategy_id}' is not defined in the manifest"
            ) from exc
        return entry.parameters

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _build_context(
        self,
        *,
        evaluation: StrategyEvaluationContext,
        plugin_metadata: StrategyMetadata,
        parameters: Mapping[str, Any],
    ) -> StrategyContext:
        watchlist = frozenset(evaluation.watchlist)
        return StrategyContext(
            features=evaluation.features,
            regime=evaluation.regime,
            gate=evaluation.gate,
            account=evaluation.account,
            config=evaluation.config,
            watchlist=watchlist,
            clock=evaluation.clock,
            seed=evaluation.seed + plugin_metadata.seed_offset,
            parameters=parameters,
        )

    def run_all(
        self,
        *,
        features: FeatureContext,
        regime: Any,
        gate: Any,
        account: Any,
        config: Any,
        clock: Any,
        watchlist: Iterable[str] | None = None,
        seed: int = 0,
    ) -> list[Any]:
        """Execute all enabled strategies and return aggregated signals."""

        if self._manifest is None:
            msg = "Strategy manifest has not been loaded"
            raise ManifestLoadError(msg)

        self._last_determinism_events = []
        self._last_allocation_outcomes = []
        self._last_candidate_trades = []
        self._manifest.validate_feature_contract(features.available_keys)
        self._manifest.validate_watchlists(features.symbols)
        resolved_watchlist: frozenset[str]
        if watchlist:
            normalised_watchlist = _normalise_symbol_set(watchlist)
            missing = normalised_watchlist - _normalise_symbol_set(features.symbols)
            if missing:
                msg = (
                    "Provided watchlist contains symbols missing from feature context: "
                    f"{sorted(missing)}"
                )
                raise ManifestValidationError(msg)
            resolved_watchlist = normalised_watchlist
        else:
            resolved_watchlist = self._manifest.resolve_watchlist(features.symbols)

        evaluation = StrategyEvaluationContext(
            features=features,
            regime=regime,
            gate=gate,
            account=account,
            config=config,
            clock=clock,
            watchlist=resolved_watchlist,
            seed=seed,
        )

        ordered_entries = sorted(
            self._manifest.enabled_strategies(),
            key=lambda item: (item[1].priority, item[0]),
        )

        determinism_meta = getattr(features, "determinism", None)
        feature_version = getattr(determinism_meta, "feature_version", None)
        data_manifest_hash = getattr(determinism_meta, "data_manifest_hash", None)
        feature_seed = getattr(determinism_meta, "seed", None)
        guarded_mode = _is_guarded_mode(gate)

        results: list[Any] = []
        allocation_candidates: list[AllocationCandidate] = []
        for strategy_id, entry in ordered_entries:
            plugin = self._plugins.get(strategy_id)
            if plugin is None:
                msg = f"Strategy '{strategy_id}' defined in manifest but not registered"
                raise StrategyRegistrationError(msg)

            plugin_metadata = plugin.metadata
            manifest_metadata = entry.metadata.to_runtime()

            if (
                manifest_metadata.name != plugin_metadata.name
                or manifest_metadata.version != plugin_metadata.version
            ):
                msg = (
                    f"Manifest metadata mismatch for strategy '{strategy_id}': "
                    f"manifest=({manifest_metadata.name}, {manifest_metadata.version}), "
                    f"plugin=({plugin_metadata.name}, {plugin_metadata.version})"
                )
                raise StrategyRegistrationError(msg)

            if manifest_metadata.required_features != plugin_metadata.required_features:
                msg = (
                    f"Required features mismatch for strategy '{strategy_id}': "
                    f"manifest={sorted(manifest_metadata.required_features)}, "
                    f"plugin={sorted(plugin_metadata.required_features)}"
                )
                raise StrategyRegistrationError(msg)

            missing = plugin_metadata.required_features - features.available_keys
            if missing:
                msg = f"Strategy '{strategy_id}' missing required features: " f"{sorted(missing)}"
                raise ManifestValidationError(msg)

            context = self._build_context(
                evaluation=evaluation,
                plugin_metadata=plugin_metadata,
                parameters=entry.parameters,
            )
            plugin.context = context
            if guarded_mode and not entry.feature_flags.get("guarded_board_required", False):
                self._emit_signal_event(
                    strategy_id=strategy_id,
                    signal=None,
                    candidate_trade=None,
                    context=context,
                    feature_flags=entry.feature_flags,
                    status="suppressed_guarded",
                    reason="guarded_mode",
                )
                continue

            try:
                signals = plugin.generate_signals(context)
            except AttributeError:
                signals = plugin.evaluate(context)

            signal_count = 0
            try:
                for signal in signals:
                    candidate_trade = self._build_candidate_trade(
                        strategy_id=strategy_id,
                        signal=signal,
                        context=context,
                    )
                    results.append(signal)
                    allocation_candidates.append(
                        AllocationCandidate(
                            strategy_id=strategy_id,
                            signal=signal,
                            priority=entry.priority,
                            weight=entry.weight,
                            parameters=entry.parameters,
                            trade=candidate_trade,
                        )
                    )
                    self._last_candidate_trades.append(candidate_trade.as_dict())
                    self._emit_signal_event(
                        strategy_id=strategy_id,
                        signal=signal,
                        candidate_trade=candidate_trade,
                        context=context,
                        feature_flags=entry.feature_flags,
                        status="generated",
                        reason=None,
                    )
                    signal_count += 1
            except BaseException as exc:  # pragma: no cover - defensive
                raise StrategyExecutionError(strategy_id, exc) from exc

            determinism_key = getattr(plugin, "determinism_key", "")
            determinism_hash = compute_deterministic_hash(
                strategy_id=strategy_id,
                determinism_key=determinism_key,
                seed=context.seed,
                watchlist=context.watchlist,
                required_features=plugin_metadata.required_features,
                feature_version=feature_version,
                data_manifest_hash=data_manifest_hash,
            )
            event_payload = {
                "event": "strategy.determinism",
                "ts": _utcnow_iso(),
                "strategy_id": strategy_id,
                "determinism_key": determinism_key,
                "deterministic_hash": determinism_hash,
                "determinism_hash": determinism_hash,
                "seed": context.seed,
                "feature_seed": feature_seed,
                "feature_version": feature_version,
                "data_manifest_hash": data_manifest_hash,
                "watchlist": sorted(context.watchlist),
                "required_features": sorted(plugin_metadata.required_features),
                "signal_count": signal_count,
                "feature_flags": dict(entry.feature_flags),
                "manifest_metadata": {
                    "name": manifest_metadata.name,
                    "version": manifest_metadata.version,
                },
                "priority": entry.priority,
            }
            self._record_determinism_event(event_payload)

        if self._allocation_policy is None:
            return results

        return self._apply_allocation(
            candidates=allocation_candidates,
            account=account,
            clock=clock,
            gate=gate,
            config=config,
            features=features,
        )

    def run_with_pipeline(
        self,
        *,
        pipeline: FeaturePipeline,
        market_frame: Mapping[str, Any] | None,
        regime: Any,
        gate: Any,
        account: Any,
        config: Any,
        clock: Any,
        watchlist: Iterable[str] | None = None,
        seed: int = 0,
    ) -> list[Any]:
        """Update the pipeline with a market frame and execute strategies."""

        features = pipeline.update(market_frame=market_frame, symbols=watchlist)
        return self.run_all(
            features=features,
            regime=regime,
            gate=gate,
            account=account,
            config=config,
            clock=clock,
            watchlist=watchlist,
            seed=seed,
        )

    def _record_determinism_event(self, payload: Mapping[str, Any]) -> None:
        self._last_determinism_events.append(payload)
        try:
            self._append_determinism_log(payload)
            self._append_determinism_metrics(payload)
        except OSError as exc:  # pragma: no cover - best-effort logging
            logger.warning("strategy.registry.determinism_log_failed", extra={"error": str(exc)})

    def _emit_signal_event(
        self,
        *,
        strategy_id: str,
        signal: Any,
        candidate_trade: CandidateTrade | None,
        context: StrategyContext,
        feature_flags: Mapping[str, bool],
        status: str,
        reason: str | None,
    ) -> None:
        payload = {
            "event": "signal.generated",
            "ts": _utcnow_iso(),
            "status": status,
            "reason": reason,
            "strategy_id": strategy_id,
            "feature_flags": dict(feature_flags),
            "seed": context.seed,
            "watchlist": sorted(context.watchlist),
        }
        if signal is not None:
            payload.update(
                {
                    "symbol": getattr(signal, "symbol", None),
                    "direction": getattr(signal, "direction", None),
                    "confidence": getattr(signal, "confidence", None),
                    "rationale": getattr(signal, "rationale", None),
                    "breakout": getattr(signal, "breakout", None),
                    "level": getattr(signal, "level", None),
                    "buffer": getattr(signal, "buffer", None),
                    "breakout_width": getattr(signal, "breakout_width", None),
                    "filter_flags": getattr(signal, "filter_flags", None),
                    "filter_block_reason": getattr(signal, "filter_block_reason", None),
                    "quality_score": getattr(signal, "quality_score", None),
                    "score": getattr(signal, "score", None),
                    "badges": getattr(signal, "badges", None),
                    "compression_high": getattr(signal, "compression_high", None),
                    "compression_low": getattr(signal, "compression_low", None),
                    "compression_range": getattr(signal, "compression_range", None),
                    "breakout_distance": getattr(signal, "breakout_distance", None),
                    "cost_estimate": getattr(signal, "cost_estimate", None),
                    "orb_high": getattr(signal, "orb_high", None),
                    "orb_low": getattr(signal, "orb_low", None),
                    "orb_width": getattr(signal, "orb_width", None),
                    "vwap": getattr(signal, "vwap", None),
                }
            )
            payload.update(_derive_signal_trade_fields(signal=signal, context=context))
        if candidate_trade is not None:
            payload["candidate"] = candidate_trade.as_dict()
            payload["candidate_id"] = candidate_trade.candidate_id
        try:
            _append_jsonl(
                self._signal_log_path,
                payload,
                max_bytes=self._signal_log_max_bytes,
                keep_bytes=self._signal_log_keep_bytes,
            )
        except OSError as exc:  # pragma: no cover - best-effort logging
            logger.warning("strategy.registry.signal_log_failed", extra={"error": str(exc)})

    def _emit_portfolio_admission_event(
        self,
        *,
        strategy_id: str,
        signal: Any,
        candidate_trade: CandidateTrade | None,
        payload: Mapping[str, Any],
        feature_flags: Mapping[str, bool],
    ) -> None:
        record = {
            "event": "portfolio.admission",
            "ts": payload.get("ts") or _utcnow_iso(),
            "strategy_id": strategy_id,
            "status": payload.get("decision"),
            "reason": payload.get("reason_code"),
            "feature_flags": dict(feature_flags),
            "allocation_decision": dict(payload),
        }
        if signal is not None:
            record.update(
                {
                    "symbol": getattr(signal, "symbol", None),
                    "direction": getattr(signal, "direction", None),
                    "confidence": getattr(signal, "confidence", None),
                    "score": getattr(signal, "score", None),
                    "quality_score": getattr(signal, "quality_score", None),
                }
            )
        if candidate_trade is not None:
            record["candidate"] = candidate_trade.as_dict()
            record["candidate_id"] = candidate_trade.candidate_id
        try:
            _append_jsonl(
                self._signal_log_path,
                record,
                max_bytes=self._signal_log_max_bytes,
                keep_bytes=self._signal_log_keep_bytes,
            )
        except OSError as exc:  # pragma: no cover - best-effort logging
            logger.warning("strategy.registry.signal_log_failed", extra={"error": str(exc)})

    def _append_determinism_log(self, payload: Mapping[str, Any]) -> None:
        _append_jsonl(
            self._determinism_log_path,
            payload,
            max_bytes=self._determinism_log_max_bytes,
            keep_bytes=self._determinism_log_keep_bytes,
        )

    def _append_determinism_metrics(self, payload: Mapping[str, Any]) -> None:
        path = self._determinism_metrics_path
        if path is None:
            return
        record = {
            "ts": payload.get("ts") or _utcnow_iso(),
            "strategy_id": payload.get("strategy_id"),
            "feature_version": payload.get("feature_version"),
            "determinism_hash": payload.get("determinism_hash"),
            "status": "ok",
            "latency_ms": payload.get("latency_ms"),
            "mode": payload.get("mode") or "unknown",
        }
        _append_jsonl(
            path,
            record,
            max_bytes=self._determinism_metrics_max_bytes,
            keep_bytes=self._determinism_metrics_keep_bytes,
        )

    def _apply_allocation(
        self,
        *,
        candidates: Iterable[AllocationCandidate],
        account: Any,
        clock: Any,
        gate: Any,
        config: Any,
        features: FeatureContext,
    ) -> list[Any]:
        policy = self._allocation_policy
        if policy is None:
            return [candidate.signal for candidate in candidates]

        materialized = tuple(candidates)
        if not materialized:
            return []

        by_symbol: dict[str, list[AllocationCandidate]] = {}
        for candidate in materialized:
            symbol = str(getattr(candidate.signal, "symbol", "UNKNOWN")).upper()
            by_symbol.setdefault(symbol, []).append(candidate)

        selected: list[Any] = []
        allocation_now = self._allocation_now(clock)
        open_positions = self._allocation_open_positions(account=account)
        for symbol, symbol_candidates in sorted(by_symbol.items()):
            context = AllocationContext(
                now=allocation_now,
                board_mode=self._allocation_board_mode(gate=gate, config=config),
                kill_switch_state=self._allocation_kill_switch_state(gate=gate, config=config),
                regime_value=self._allocation_regime_value(features=features, symbol=symbol),
                open_positions=open_positions,
            )
            allocation = policy.allocate(candidates=symbol_candidates, context=context)
            self._record_allocation_outcomes(
                allocation=allocation.outcomes,
                candidates=symbol_candidates,
                context=context,
            )
            selected.extend(candidate.signal for candidate in allocation.selected)

        return selected

    def _record_allocation_outcomes(
        self,
        *,
        allocation: Iterable[AllocationOutcome],
        candidates: Iterable[AllocationCandidate],
        context: AllocationContext,
    ) -> None:
        candidate_lookup = {
            (
                candidate.strategy_id,
                str(getattr(candidate.signal, "symbol", "UNKNOWN")).strip().upper() or "UNKNOWN",
            ): candidate
            for candidate in candidates
        }
        context_payload = {
            "ts": context.now.isoformat().replace("+00:00", "Z"),
            "board_mode": context.board_mode,
            "kill_switch_state": context.kill_switch_state,
            "regime_value": context.regime_value,
            "open_position_count": len(context.open_positions),
        }
        for outcome in allocation:
            payload = outcome.as_dict()
            payload.update(context_payload)
            self._last_allocation_outcomes.append(payload)

            candidate = candidate_lookup.get((outcome.strategy_id, outcome.symbol))
            if candidate is None:
                continue

            feature_flags: Mapping[str, bool] = {}
            if self._manifest is not None:
                entry = self._manifest.strategies.get(outcome.strategy_id)
                if entry is not None:
                    feature_flags = entry.feature_flags

            self._emit_portfolio_admission_event(
                strategy_id=outcome.strategy_id,
                signal=candidate.signal,
                candidate_trade=candidate.trade,
                payload=payload,
                feature_flags=feature_flags,
            )

    def _build_candidate_trade(
        self,
        *,
        strategy_id: str,
        signal: Any,
        context: StrategyContext,
    ) -> CandidateTrade:
        trade_fields = _derive_signal_trade_fields(signal=signal, context=context)
        allocation_metadata: Mapping[str, Any] = {}
        if self._allocation_policy is not None:
            allocation_metadata = self._allocation_policy.candidate_metadata(strategy_id)
        timestamp = _iso_or_none(getattr(signal, "timestamp", None)) or _iso_or_none(
            getattr(getattr(context, "clock", None), "now", None)
        ) or _utcnow_iso()
        symbol = str(getattr(signal, "symbol", "") or "").strip().upper() or "UNKNOWN"
        side = str(getattr(signal, "direction", "") or "").strip().lower() or "unknown"
        session_tag = getattr(signal, "session_tag", None)
        metadata = {
            "rationale": getattr(signal, "rationale", None),
            "breakout": getattr(signal, "breakout", None),
            "level": getattr(signal, "level", None),
            "buffer": getattr(signal, "buffer", None),
            "badges": getattr(signal, "badges", None),
            "expire_at": trade_fields.get("expire_at"),
            "ttl_bars": trade_fields.get("ttl_bars"),
            "target_r_multiple": trade_fields.get("target_r_multiple"),
            "slippage_std": trade_fields.get("slippage_std"),
        }
        candidate_id = _candidate_id_from_parts(
            strategy_id,
            symbol,
            side,
            timestamp,
            trade_fields.get("entry"),
            trade_fields.get("stop"),
            trade_fields.get("target"),
        )
        return CandidateTrade(
            candidate_id=candidate_id,
            strategy_id=strategy_id,
            symbol=symbol,
            side=side,
            timestamp=timestamp,
            entry=_coerce_float(trade_fields.get("entry")),
            stop=_coerce_float(trade_fields.get("stop")),
            target=_coerce_float(trade_fields.get("target")),
            confidence=_coerce_float(getattr(signal, "confidence", None)),
            expected_holding_minutes=_coerce_float(
                allocation_metadata.get("expected_holding_minutes")
            ),
            portfolio_group=str(allocation_metadata.get("portfolio_group") or "").strip(),
            exposure_bucket=str(allocation_metadata.get("exposure_bucket") or "").strip(),
            estimated_cost=_coerce_float(trade_fields.get("cost_estimate")),
            quality_score=_coerce_float(getattr(signal, "quality_score", None)),
            regime_fit=_coerce_float(getattr(signal, "score", None)),
            session_tag=str(session_tag).strip().lower() if session_tag is not None else None,
            atr_value=_coerce_float(getattr(signal, "atr_value", None)),
            trend_value=_coerce_float(getattr(signal, "trend_value", None)),
            cost_ratio=_coerce_float(getattr(signal, "cost_ratio", None)),
            metadata={key: value for key, value in metadata.items() if value is not None},
        )

    @staticmethod
    def _allocation_now(clock: Any) -> datetime:
        now = getattr(clock, "now", None)
        if isinstance(now, datetime):
            return _as_utc(now)
        return datetime.now(timezone.utc)

    @staticmethod
    def _allocation_open_positions(account: Any) -> tuple[AllocationActivePosition, ...]:
        raw_positions = getattr(account, "positions", None)
        if raw_positions is None:
            raw_positions = getattr(account, "open_positions", None)
        if raw_positions is None or isinstance(raw_positions, (str, bytes, Mapping)):
            return ()
        if not isinstance(raw_positions, Iterable):
            return ()

        positions: list[AllocationActivePosition] = []
        for raw in raw_positions:
            if isinstance(raw, Mapping):
                position_id = str(raw.get("position_id") or raw.get("id") or "").strip()
                strategy_id = str(raw.get("strategy_id") or "").strip()
                symbol = str(raw.get("symbol") or "").strip().upper()
                direction = str(raw.get("direction") or "").strip().lower()
                opened_at_raw = raw.get("opened_at")
            else:
                position_id = str(
                    getattr(raw, "position_id", "") or getattr(raw, "id", "") or ""
                ).strip()
                strategy_id = str(getattr(raw, "strategy_id", "") or "").strip()
                symbol = str(getattr(raw, "symbol", "") or "").strip().upper()
                direction = str(getattr(raw, "direction", "") or "").strip().lower()
                opened_at_raw = getattr(raw, "opened_at", None)
            if not symbol:
                continue
            opened_at: datetime | None = None
            if isinstance(opened_at_raw, datetime):
                opened_at = _as_utc(opened_at_raw)
            elif hasattr(opened_at_raw, "to_pydatetime"):
                converted = opened_at_raw.to_pydatetime()
                if isinstance(converted, datetime):
                    opened_at = _as_utc(converted)
            positions.append(
                AllocationActivePosition(
                    strategy_id=strategy_id,
                    symbol=symbol,
                    direction=direction,
                    opened_at=opened_at,
                    position_id=position_id,
                )
            )
        return tuple(positions)

    @staticmethod
    def _allocation_board_mode(*, gate: Any, config: Any) -> str:
        direct = getattr(gate, "board_mode", None)
        if isinstance(direct, str) and direct.strip():
            return direct.strip().lower()

        cfg_mode = getattr(config, "board_mode", None)
        if isinstance(cfg_mode, str) and cfg_mode.strip():
            return cfg_mode.strip().lower()

        market = getattr(gate, "market", None)
        readiness = getattr(market, "profit_readiness_status", None)
        if isinstance(readiness, str):
            lowered = readiness.strip().lower()
            if lowered in {"guarded", "halted"}:
                return lowered
        return "normal"

    @staticmethod
    def _allocation_kill_switch_state(*, gate: Any, config: Any) -> str:
        risk = getattr(gate, "risk", None)
        explicit = getattr(risk, "kill_switch_recommendation", None)
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip().lower()
        if bool(getattr(risk, "reduce_only", False)):
            return "soft_stop"

        cfg_state = getattr(config, "kill_switch_state", None)
        if isinstance(cfg_state, str) and cfg_state.strip():
            return cfg_state.strip().lower()
        return "normal"

    @staticmethod
    def _allocation_regime_value(*, features: FeatureContext, symbol: str) -> float | None:
        try:
            regime = features.lookup(symbol=symbol, feature="regime_trend_1h", timeframe="1h")
        except Exception:
            return None
        if isinstance(regime, (int, float)):
            return float(regime)
        getter = getattr(regime, "iloc", None)
        if getter is not None:
            try:
                return float(regime.iloc[-1])
            except Exception:
                return None
        try:
            return float(regime)
        except Exception:
            return None
