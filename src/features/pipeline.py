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

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping

import yaml
import pandas as pd

_TIMEFRAME_RULES: Mapping[str, str] = {
    "5m": "5t",
    "15m": "15t",
    "30m": "30t",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}

__all__ = [
    "FeatureContext",
    "FeaturePipeline",
    "IndicatorDefinition",
    "FeatureDeterminismMetadata",
    "RebuildReport",
]


class FeatureLookupError(KeyError):
    """Raised when attempting to access a feature that was not computed."""


@dataclass(slots=True, frozen=True)
class FeatureDeterminismMetadata:
    """Determinism metadata propagated through the feature pipeline."""

    feature_version: str
    data_manifest_hash: str
    seed: int = 0
    replay_window: str | None = None

    def cache_key(self, *, symbol: str, timeframe: str) -> str:
        """Return a deterministic cache key including versioned inputs."""

        return f"{symbol}:{timeframe}:{self.feature_version}:{self.data_manifest_hash}"

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def as_record(self) -> Mapping[str, Any]:
        """Return a serialisable representation for telemetry/audit hooks."""

        return {
            "feature_version": self.feature_version,
            "data_manifest_hash": self.data_manifest_hash,
            "seed": self.seed,
            "replay_window": self.replay_window,
            "ts": self._utcnow_iso(),
        }


@dataclass(slots=True)
class FeatureContext:
    """Immutable snapshot of feature availability for strategy evaluation."""

    symbols: frozenset[str]
    timeframes: frozenset[str]
    available_keys: frozenset[str]
    determinism: FeatureDeterminismMetadata | None = None
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

    def __init__(
        self,
        *,
        config: Mapping[str, Any],
        feature_version: str | None = None,
        data_manifest_hash: str | None = None,
        seed: int = 0,
    ):
        self._config = config
        self._feature_version = feature_version or self._load_feature_set_version(Path("config") / "features" / "feature_versions.yaml")
        self._data_manifest_hash = data_manifest_hash or self._compute_data_manifest_hash(Path("reports") / "data_manifest.json")
        self._determinism = FeatureDeterminismMetadata(
            feature_version=self._feature_version,
            data_manifest_hash=self._data_manifest_hash,
            seed=seed,
        )
        self._indicators: MutableMapping[str, IndicatorDefinition] = {}
        self._available_keys: set[str] = set()
        self._store: MutableMapping[str, MutableMapping[str, MutableMapping[str, Any]]] = {}

        pipeline_cfg = config.get("pipeline", {})
        resample_cfg = pipeline_cfg.get("resample", {})
        timeframes = tuple(resample_cfg.get("timeframes", []))
        default_tf_minutes = pipeline_cfg.get("default_timeframe_minutes", 5)
        self._default_timeframe = f"{default_tf_minutes}m"
        self._timeframes = frozenset(timeframes)
        base_price_keys = {
            f"open_{self._default_timeframe}",
            f"high_{self._default_timeframe}",
            f"low_{self._default_timeframe}",
            f"close_{self._default_timeframe}",
            f"volume_{self._default_timeframe}",
        }
        self._context = FeatureContext(
            symbols=frozenset(),
            timeframes=self._timeframes,
            available_keys=frozenset(base_price_keys),
            determinism=self._determinism,
        )

        self._available_keys.update(base_price_keys)
        self._load_enabled_indicators()

    # ------------------------------------------------------------------
    # Determinism helpers
    # ------------------------------------------------------------------
    def _load_feature_set_version(self, path: Path) -> str:
        """Return the feature set version defined in the version map."""

        if not path.exists():
            return "unversioned"

        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:  # pragma: no cover - defensive fallback
            return "unversioned"

        version = payload.get("feature_set_version") or payload.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()
        return "unversioned"

    def _compute_data_manifest_hash(self, path: Path) -> str:
        """Compute a stable hash of the data manifest for cache keys."""

        if not path.exists():
            return "missing"

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _resample(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Return OHLCV frame resampled to the requested timeframe."""

        rule = _TIMEFRAME_RULES.get(timeframe, timeframe)
        aggregated = (
            df.resample(rule)
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
        )
        return aggregated

    def _compute_indicator(self, indicator: IndicatorDefinition, frame: pd.DataFrame) -> Mapping[str, pd.Series]:
        """Compute a single indicator over the provided price frame."""

        close = frame["close"]
        high = frame["high"]
        low = frame["low"]
        params = indicator.parameters
        window = int(params.get("window", params.get("period", 14)))
        outputs: dict[str, pd.Series] = {}

        def _ema_slope(series: pd.Series, span: int) -> pd.Series:
            ema = series.ewm(span=span, adjust=False).mean()
            return ema.diff()

        if indicator.identifier.startswith("sma"):
            series = close.rolling(window=window, min_periods=window).mean()
            outputs[indicator.output_keys["default"]] = series
        elif indicator.identifier.startswith("ema") and indicator.identifier != "ema55_slope":
            series = close.ewm(span=window, adjust=False).mean()
            outputs[indicator.output_keys["default"]] = series
        elif indicator.identifier.startswith("rsi"):
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(window=window, min_periods=window).mean()
            loss = -delta.clip(upper=0).rolling(window=window, min_periods=window).mean()
            rs = gain / loss.replace(0, pd.NA)
            rsi = 100 - (100 / (1 + rs))
            outputs[indicator.output_keys["default"]] = rsi
        elif indicator.identifier.startswith("atr"):
            prev_close = close.shift(1)
            tr = pd.concat(
                [
                    high - low,
                    (high - prev_close).abs(),
                    (low - prev_close).abs(),
                ],
                axis=1,
            ).max(axis=1)
            atr = tr.rolling(window=window, min_periods=window).mean()
            outputs[indicator.output_keys["default"]] = atr
        elif indicator.identifier.startswith("ema55_slope"):
            slope = _ema_slope(close, span=window)
            outputs[indicator.output_keys["default"]] = slope
        elif indicator.identifier.startswith("donchian"):
            upper = close.rolling(window=window, min_periods=window).max()
            lower = close.rolling(window=window, min_periods=window).min()
            mid = (upper + lower) / 2
            outputs[indicator.output_keys.get("upper", "upper")] = upper
            outputs[indicator.output_keys.get("lower", "lower")] = lower
            outputs[indicator.output_keys.get("mid", "mid")] = mid
        elif indicator.identifier.startswith("session_tag"):
            def _session_label(ts: pd.Timestamp) -> str:
                hour = ts.hour
                if 0 <= hour < 7:
                    return "asia"
                if 7 <= hour < 12:
                    return "london"
                if 12 <= hour < 20:
                    return "newyork"
                return "overlap"

            outputs[indicator.output_keys["default"]] = frame.index.to_series().map(_session_label)
        elif indicator.identifier.startswith("regime_trend"):
            slope = close.ewm(span=window, adjust=False).mean().diff()
            regime = slope.apply(lambda v: 1 if v > 0 else (-1 if v < 0 else 0))
            outputs[indicator.output_keys["default"]] = regime
        else:  # pragma: no cover - defensive path for future indicators
            raise ValueError(f"Indicator '{indicator.identifier}' not supported in PoC pipeline")

        return outputs

    def compute_feature_matrix(self, *, symbol: str, price_df: pd.DataFrame) -> pd.DataFrame:
        """Return a feature matrix aligned to the base timeframe index.

        The returned dataframe is indexed by the original ``timestamp`` index
        and contains one column per expanded feature key (``<alias>_<tf>``).
        Higher-timeframe indicators are forward-filled to the base index to
        simplify per-bar strategy evaluation.
        """

        if price_df.empty:
            return pd.DataFrame()

        frame = price_df.copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame = frame.set_index("timestamp").sort_index()

        feature_columns: dict[str, pd.Series] = {}
        for indicator in self._indicators.values():
            for timeframe in indicator.timeframes:
                resampled = self._resample(frame, timeframe) if timeframe != self._default_timeframe else frame
                computed = self._compute_indicator(indicator, resampled)
                for alias, series in computed.items():
                    column_name = f"{alias}_{timeframe}"
                    aligned = series.rename(column_name)
                    if timeframe != self._default_timeframe:
                        aligned = aligned.reindex(frame.index, method="ffill")
                    feature_columns[column_name] = aligned

        matrix = pd.DataFrame(feature_columns, index=frame.index)
        # add base OHLCV columns for strategy use
        matrix[f"open_{self._default_timeframe}"] = frame["open"]
        matrix[f"high_{self._default_timeframe}"] = frame["high"]
        matrix[f"low_{self._default_timeframe}"] = frame["low"]
        matrix[f"close_{self._default_timeframe}"] = frame["close"]
        matrix[f"volume_{self._default_timeframe}"] = frame["volume"]
        # refresh context so manifest validation can see the symbol set
        self._context = FeatureContext(
            symbols=frozenset({symbol}),
            timeframes=self._timeframes,
            available_keys=frozenset(self._available_keys),
            determinism=self._determinism,
            _store=self._context._store,
        )
        return matrix

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_config_file(
        cls,
        path: str | Path,
        *,
        feature_version: str | None = None,
        data_manifest_hash: str | None = None,
        seed: int = 0,
    ) -> "FeaturePipeline":
        """Instantiate the pipeline from a YAML configuration file."""

        cfg_path = Path(path)
        with cfg_path.open("r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh.read())
        return cls(
            config=config,
            feature_version=feature_version,
            data_manifest_hash=data_manifest_hash,
            seed=seed,
        )

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
            determinism=self._determinism,
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
            determinism=self._determinism,
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

    def feature_cache_key(self, *, symbol: str, timeframe: str) -> str:
        """Return the deterministic cache key for a symbol/timeframe pair."""

        return self._determinism.cache_key(symbol=symbol, timeframe=timeframe)

    @property
    def feature_version(self) -> str:
        """Return the active feature set version."""

        return self._feature_version

    @property
    def data_manifest_hash(self) -> str:
        """Return the hash of the data manifest used for cache keys."""

        return self._data_manifest_hash

    @property
    def determinism(self) -> FeatureDeterminismMetadata:
        """Expose determinism metadata for downstream components."""

        return self._determinism

    @property
    def context(self) -> FeatureContext:
        """Return the latest :class:`FeatureContext` snapshot."""

        return self._context
