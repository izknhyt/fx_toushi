"""Feature pipeline scaffolding for registering indicator outputs.

The implementation in this module intentionally focuses on the static
contract surfaced to downstream components (``FeatureContext`` and the
normalized ``available_keys`` set).  The detailed design calls for a
stateful pipeline that performs resampling, invokes indicator plugins,
and materialises feature frames.  The current repository snapshot does
not ship concrete indicator implementations, however the surrounding
tests expect the configuration loader and naming normalisation rules to
be in place so that strategy manifests can validate their
``required_features`` declarations.

``FeaturePipeline`` therefore parses ``config/feature_pipeline.yaml``
and registers enabled indicator entries.  Each indicator contributes one
or more base output keys which are expanded across their configured
timeframes to produce the canonical ``<output_key>_<timeframe>`` naming
scheme.  The resulting set is exposed on :class:`FeatureContext` and is
used by smoke tests to cross-check the strategy manifest contract.

Future implementation packets can replace the lightweight placeholder
methods (``update``/``rebuild_range``/``get_feature_frame``) with the
full data processing logic without breaking the public API exercised by
tests and other modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping

import yaml

__all__ = [
    "FeatureContext",
    "FeaturePipeline",
    "IndicatorDefinition",
    "RebuildReport",
]


class FeatureLookupError(KeyError):
    """Raised when attempting to access a feature that was not computed."""


@dataclass(slots=True)
class FeatureContext:
    """Immutable snapshot of feature availability for strategy evaluation."""

    symbols: frozenset[str]
    timeframes: frozenset[str]
    available_keys: frozenset[str]
    _store: Mapping[str, Mapping[str, Mapping[str, Any]]] = field(
        default_factory=dict, repr=False
    )

    def lookup(self, *, symbol: str, feature: str, timeframe: str) -> Any:
        """Return the feature payload for ``symbol``/``timeframe``/``feature``.

        The scaffold tracks availability only, so the payload defaults to
        ``None`` unless future packets populate ``_store``.  Attempting to
        access a missing key raises :class:`FeatureLookupError` to mirror
        the detailed design contract.
        """

        try:
            return self._store[symbol][timeframe][feature]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise FeatureLookupError(symbol, timeframe, feature) from exc

    def get_latest(self, *, symbol: str, feature: str, timeframe: str) -> Any:
        """Alias for :meth:`lookup` used by strategy helpers."""

        return self.lookup(symbol=symbol, feature=feature, timeframe=timeframe)

    def feature_frame(self, symbol: str) -> Mapping[str, Mapping[str, Any]]:
        """Return the time-frame keyed feature mapping for ``symbol``."""

        return self._store.get(symbol, {})


@dataclass(slots=True, frozen=True)
class IndicatorDefinition:
    """Normalised indicator description derived from configuration entries."""

    identifier: str
    timeframes: tuple[str, ...]
    output_keys: Mapping[str, str]
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def expanded_feature_keys(self) -> frozenset[str]:
        """Return the ``<output_key>_<timeframe>`` combinations for the indicator."""

        return frozenset(
            f"{output_key}_{timeframe}"
            for timeframe in self.timeframes
            for output_key in self.output_keys.values()
        )


@dataclass(slots=True)
class RebuildReport:
    """Summary returned by :meth:`FeaturePipeline.rebuild_range`."""

    symbols: frozenset[str]
    start: Any | None
    end: Any | None
    bars_processed: int = 0


class FeaturePipeline:
    """Configuration-driven feature pipeline scaffold."""

    def __init__(self, *, config: Mapping[str, Any]):
        self._config = config
        self._indicators: MutableMapping[str, IndicatorDefinition] = {}
        self._available_keys: set[str] = set()
        self._store: MutableMapping[str, MutableMapping[str, MutableMapping[str, Any]]] = {}

        pipeline_cfg = config.get("pipeline", {})
        resample_cfg = pipeline_cfg.get("resample", {})
        timeframes = tuple(resample_cfg.get("timeframes", []))
        self._timeframes = frozenset(timeframes)
        self._context = FeatureContext(
            symbols=frozenset(),
            timeframes=self._timeframes,
            available_keys=frozenset(),
        )

        self._load_enabled_indicators()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_config_file(cls, path: str | Path) -> "FeaturePipeline":
        """Instantiate the pipeline from a YAML configuration file."""

        cfg_path = Path(path)
        with cfg_path.open("r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh.read())
        return cls(config=config)

    # ------------------------------------------------------------------
    # Indicator registration
    # ------------------------------------------------------------------
    def register_indicator(self, indicator: IndicatorDefinition) -> None:
        """Register an indicator and merge its feature keys into the context."""

        if indicator.identifier in self._indicators:
            raise ValueError(f"Indicator '{indicator.identifier}' already registered")

        self._indicators[indicator.identifier] = indicator
        self._available_keys.update(indicator.expanded_feature_keys())
        self._context = FeatureContext(
            symbols=self._context.symbols,
            timeframes=self._timeframes,
            available_keys=frozenset(self._available_keys),
            _store=self._context._store,
        )

    def _load_enabled_indicators(self) -> None:
        indicators_cfg: Mapping[str, Mapping[str, Any]] = self._config.get("indicators", {})
        for identifier, raw_cfg in indicators_cfg.items():
            if not raw_cfg.get("enabled", False):
                continue
            timeframes = tuple(raw_cfg.get("timeframes", ()))
            if not timeframes:
                raise ValueError(f"Indicator '{identifier}' is enabled but defines no timeframes")

            if "output_key" in raw_cfg:
                output_keys: Mapping[str, str] = {"default": str(raw_cfg["output_key"])}
            elif "output_keys" in raw_cfg:
                output_keys = {
                    str(column): str(alias)
                    for column, alias in raw_cfg["output_keys"].items()
                }
            else:  # pragma: no cover - schema validation should prevent this
                raise ValueError(
                    f"Indicator '{identifier}' is enabled but missing output key information"
                )

            parameters = {
                key: value
                for key, value in raw_cfg.items()
                if key not in {"enabled", "timeframes", "output_key", "output_keys"}
            }

            definition = IndicatorDefinition(
                identifier=identifier,
                timeframes=timeframes,
                output_keys=output_keys,
                parameters=parameters,
            )
            self.register_indicator(definition)

    # ------------------------------------------------------------------
    # Pipeline operations
    # ------------------------------------------------------------------
    def update(
        self,
        market_frame: Mapping[str, Any] | None = None,
        *,
        symbols: Iterable[str] | None = None,
    ) -> FeatureContext:
        """Return a context snapshot after ingesting ``market_frame``.

        The scaffold records the requested ``symbols`` (if any) so the
        resulting :class:`FeatureContext` aligns with expectations from the
        detailed design.  Concrete indicator calculations will be wired in
        future packets.
        """

        if symbols is None:
            symbol_set: frozenset[str] = self._context.symbols
        else:
            symbol_set = frozenset(symbols)

        self._context = FeatureContext(
            symbols=symbol_set,
            timeframes=self._timeframes,
            available_keys=frozenset(self._available_keys),
            _store=self._context._store,
        )
        return self._context

    def rebuild_range(
        self,
        symbols: Iterable[str],
        start: Any | None,
        end: Any | None,
    ) -> RebuildReport:
        """Placeholder implementation for historical rebuilds."""

        symbol_set = frozenset(symbols)
        return RebuildReport(symbols=symbol_set, start=start, end=end, bars_processed=0)

    def get_feature_frame(
        self,
        symbol: str,
        *,
        timeframe: str | None = None,
    ) -> Mapping[str, Any] | Mapping[str, Mapping[str, Any]]:
        """Return the stored feature view for ``symbol``.

        When ``timeframe`` is provided the method narrows the view to a
        single timeframe.  The scaffold returns empty dictionaries because
        no indicators have been materialised yet; concrete implementations
        can populate ``self._store`` without changing the signature.
        """

        frame = self._context.feature_frame(symbol)
        if timeframe is None:
            return frame
        return frame.get(timeframe, {})

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    @property
    def available_keys(self) -> frozenset[str]:
        """Return the set of ``<output_key>_<timeframe>`` feature names."""

        return frozenset(self._available_keys)

    @property
    def indicators(self) -> Mapping[str, IndicatorDefinition]:
        """Expose the registered indicators for inspection/testing."""

        return dict(self._indicators)

    @property
    def context(self) -> FeatureContext:
        """Return the latest :class:`FeatureContext` snapshot."""

        return self._context

