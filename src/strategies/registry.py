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

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, MutableMapping, Sequence

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from src.features.pipeline import FeatureContext
from src.strategies.base import StrategyContext, StrategyMetadata, StrategyPluginProtocol

__all__ = [
    "ManifestLoadError",
    "ManifestValidationError",
    "StrategyExecutionError",
    "StrategyRegistryError",
    "StrategyRegistrationError",
    "StrategyManifest",
    "StrategyEngine",
]


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
    parameters: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("feature_flags")
    @classmethod
    def _normalise_feature_flags(cls, value: Mapping[str, Any]) -> Mapping[str, bool]:
        normalised: dict[str, bool] = {}
        for key, flag in value.items():
            normalised[str(key)] = bool(flag)
        return normalised

    @property
    def enabled_feature_flags(self) -> frozenset[str]:
        """Return the subset of feature flags that are enabled."""

        return frozenset(
            key for key, enabled in self.feature_flags.items() if bool(enabled)
        )


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
    def _ensure_strategies(cls, value: Mapping[str, StrategyEntry]) -> MutableMapping[str, StrategyEntry]:
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
    def _validate_weights(self) -> "StrategyManifest":
        total_weight = sum(
            entry.weight for entry in self.strategies.values() if entry.enabled
        )
        if total_weight > 1.0 + 1e-9:
            msg = "Sum of enabled strategy weights must not exceed 1.0"
            raise ValueError(msg)
        return self

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StrategyManifest":
        """Validate and construct a manifest from an in-memory mapping."""

        try:
            return cls.model_validate(payload)
        except ValidationError as exc:  # pragma: no cover - defensive
            raise ManifestValidationError("Strategy manifest validation failed", errors=exc.errors()) from exc

    @classmethod
    def load(cls, path: str | Path) -> "StrategyManifest":
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

        return cls.from_dict(payload)

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
                strategy_id: sorted(features)
                for strategy_id, features in missing_map.items()
            }
            msg = "Strategy manifest references unavailable features"
            raise ManifestValidationError(f"{msg}: {details}")


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

    def __init__(self) -> None:
        self._plugins: dict[str, StrategyPluginProtocol] = {}
        self._manifest: StrategyManifest | None = None

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

    def get_parameters(self, strategy_id: str) -> Mapping[str, Any]:
        """Return manifest parameters for ``strategy_id`` (if available)."""

        if self._manifest is None:
            msg = "Strategy manifest has not been loaded"
            raise ManifestLoadError(msg)

        try:
            entry = self._manifest.strategies[strategy_id]
        except KeyError as exc:  # pragma: no cover - defensive
            raise StrategyRegistrationError(f"Strategy '{strategy_id}' is not defined in the manifest") from exc
        return entry.parameters

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _build_context(self, *, evaluation: StrategyEvaluationContext, plugin_metadata: StrategyMetadata) -> StrategyContext:
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

        self._manifest.validate_feature_contract(features.available_keys)

        evaluation = StrategyEvaluationContext(
            features=features,
            regime=regime,
            gate=gate,
            account=account,
            config=config,
            clock=clock,
            watchlist=watchlist or features.symbols,
            seed=seed,
        )

        ordered_entries = sorted(
            self._manifest.enabled_strategies(),
            key=lambda item: (item[1].priority, item[0]),
        )

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
                msg = (
                    f"Strategy '{strategy_id}' missing required features: "
                    f"{sorted(missing)}"
                )
                raise ManifestValidationError(msg)

            context = self._build_context(
                evaluation=evaluation,
                plugin_metadata=plugin_metadata,
            )

            try:
                for signal in plugin.evaluate(context):
                    results.append(signal)
            except BaseException as exc:  # pragma: no cover - defensive
                raise StrategyExecutionError(strategy_id, exc) from exc

        return results

