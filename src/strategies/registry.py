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
from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol

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


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


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
        self._determinism_log_path = (
            Path("logs") / "strategy" / "registry.log"
            if determinism_log_path is None
            else Path(determinism_log_path)
        )
        if determinism_metrics_path is not None:
            self._determinism_metrics_path = Path(determinism_metrics_path)
        else:
            env_path = os.getenv("TRADECTL_DETERMINISM_METRICS")
            self._determinism_metrics_path = Path(env_path) if env_path else DEFAULT_DETERMINISM_METRICS
        signal_env = os.getenv("TRADECTL_SIGNAL_EVENT_LOG")
        self._signal_log_path = (
            Path(signal_env) if signal_env else DEFAULT_SIGNAL_EVENT_LOG
        )

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
        self, *, evaluation: StrategyEvaluationContext, plugin_metadata: StrategyMetadata
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
        self._manifest.validate_feature_contract(features.available_keys)
        self._manifest.validate_watchlists(features.symbols)
        resolved_watchlist = watchlist or self._manifest.resolve_watchlist(features.symbols)

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
            )
            plugin.context = context
            if guarded_mode and not entry.feature_flags.get("guarded_board_required", False):
                self._emit_signal_event(
                    strategy_id=strategy_id,
                    signal=None,
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
                    results.append(signal)
                    self._emit_signal_event(
                        strategy_id=strategy_id,
                        signal=signal,
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
                strategy_config=entry.parameters,
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

        return results

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
                    "score": getattr(signal, "score", None),
                    "badges": getattr(signal, "badges", None),
                }
            )
        try:
            _append_jsonl(self._signal_log_path, payload)
        except OSError as exc:  # pragma: no cover - best-effort logging
            logger.warning("strategy.registry.signal_log_failed", extra={"error": str(exc)})

    def _append_determinism_log(self, payload: Mapping[str, Any]) -> None:
        path = self._determinism_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

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
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
