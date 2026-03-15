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
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .cache import FeatureCacheStore

_TIMEFRAME_RULES: Mapping[str, str] = {
    "5m": "5t",
    "15m": "15t",
    "30m": "30t",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}

DEFAULT_FEATURE_CACHE_METRICS = Path("metrics") / "feature_cache.jsonl"
_ALWAYS_ON_INDICATORS = frozenset({"sma_20", "ema_fast", "ema_slow", "rsi_14", "atr_14"})

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
    _store: Mapping[str, Mapping[str, Mapping[str, Any]]] = field(default_factory=dict, repr=False)

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
        pipeline_steps: Sequence[Mapping[str, Any]] | None = None,
        cache_store: FeatureCacheStore | None = None,
        cache_metrics_path: Path | None = None,
    ):
        self._config = config
        self._feature_version = feature_version or self._load_feature_set_version(
            Path("config") / "features" / "feature_versions.yaml"
        )
        self._data_manifest_hash = data_manifest_hash or self._compute_data_manifest_hash(
            Path("reports") / "data_manifest.json"
        )
        self._determinism = FeatureDeterminismMetadata(
            feature_version=self._feature_version,
            data_manifest_hash=self._data_manifest_hash,
            seed=seed,
        )
        cache_metrics_env = os.getenv("FEATURE_CACHE_METRICS_PATH")
        resolved_cache_metrics = cache_metrics_path
        if resolved_cache_metrics is None and cache_metrics_env:
            resolved_cache_metrics = Path(cache_metrics_env)
        if resolved_cache_metrics is None:
            resolved_cache_metrics = DEFAULT_FEATURE_CACHE_METRICS
        self._cache_store = cache_store or FeatureCacheStore(
            metrics_path=resolved_cache_metrics
        )
        self._rng = np.random.default_rng(self._determinism.seed)
        self._pipeline_steps = tuple(pipeline_steps or ())
        self._indicators: MutableMapping[str, IndicatorDefinition] = {}
        self._available_keys: set[str] = set()
        self._store: MutableMapping[str, MutableMapping[str, MutableMapping[str, Any]]] = {}
        self._metrics_path = Path(os.getenv("PIPELINE_METRICS_PATH", "metrics/pipeline.jsonl"))

        pipeline_cfg = config.get("pipeline", {})
        resample_cfg = pipeline_cfg.get("resample", {})
        timeframes = tuple(resample_cfg.get("timeframes", []))
        default_tf_minutes = pipeline_cfg.get("default_timeframe_minutes", 5)
        self._default_timeframe = f"{default_tf_minutes}m"
        self._timeframes = frozenset(timeframes)
        self._lookback_bars = int(pipeline_cfg.get("lookback_bars", 0) or 0)
        self._resample_enabled = bool(resample_cfg.get("enabled", True))
        self._max_workers = int(pipeline_cfg.get("max_workers", 4) or 4)
        if self._max_workers < 1:
            self._max_workers = 1
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

        if not self._resample_enabled or timeframe == self._default_timeframe:
            return df
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

    def _compute_indicator(
        self, indicator: IndicatorDefinition, frame: pd.DataFrame
    ) -> Mapping[str, pd.Series]:
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
            series = close.rolling(window=window, min_periods=1).mean()
            outputs[indicator.output_keys["default"]] = series
        elif indicator.identifier.startswith("ema") and indicator.identifier != "ema55_slope":
            series = close.ewm(span=window, adjust=False).mean()
            outputs[indicator.output_keys["default"]] = series
        elif indicator.identifier.startswith("rsi"):
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(window=window, min_periods=window).mean()
            loss = -delta.clip(upper=0).rolling(window=window, min_periods=window).mean()
            safe_loss = loss.replace(0, 1e-9)
            rs = gain / safe_loss
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
        elif indicator.identifier.startswith("bollinger"):
            stddev = float(params.get("stddev", 2.0))
            mid = close.rolling(window=window, min_periods=window).mean()
            std = close.rolling(window=window, min_periods=window).std()
            outputs[indicator.output_keys["upper"]] = mid + stddev * std
            outputs[indicator.output_keys["middle"]] = mid
            outputs[indicator.output_keys["lower"]] = mid - stddev * std
        elif indicator.identifier.startswith("macd"):
            fast = close.ewm(span=int(params.get("fast_period", 12)), adjust=False).mean()
            slow = close.ewm(span=int(params.get("slow_period", 26)), adjust=False).mean()
            macd_line = fast - slow
            signal = macd_line.ewm(span=int(params.get("signal_period", 9)), adjust=False).mean()
            hist = macd_line - signal
            outputs[indicator.output_keys["line"]] = macd_line
            outputs[indicator.output_keys["signal"]] = signal
            outputs[indicator.output_keys["histogram"]] = hist
        elif indicator.identifier.startswith("donchian"):
            upper = high.rolling(window=window, min_periods=window).max().shift(1)
            lower = low.rolling(window=window, min_periods=window).min().shift(1)
            mid = (upper + lower) / 2
            outputs[indicator.output_keys.get("upper", "upper")] = upper
            outputs[indicator.output_keys.get("lower", "lower")] = lower
            outputs[indicator.output_keys.get("mid", "mid")] = mid
        elif indicator.identifier.startswith("zscore"):
            mean = close.rolling(window=window, min_periods=window).mean()
            std = close.rolling(window=window, min_periods=window).std().replace(0, np.nan)
            zscore = (close - mean) / std
            outputs[indicator.output_keys["default"]] = zscore
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

    def _fill_missing_series(self, series: pd.Series, *, column: str) -> pd.Series:
        del column
        if series.empty or not series.isna().any():
            return series
        # Preserve leading NaNs to avoid inventing synthetic price-scale values
        # for warm-up periods (e.g., Donchian/ATR before enough history exists).
        return series.ffill()

    def _fill_missing_matrix(self, matrix: pd.DataFrame) -> pd.DataFrame:
        if matrix.empty:
            return matrix
        filled = matrix.copy()
        for column in filled.columns:
            filled[column] = self._fill_missing_series(filled[column], column=column)
        return filled

    @staticmethod
    def _parse_timestamp_series(series: pd.Series) -> pd.Series:
        parsed = pd.to_datetime(series, utc=True, errors="coerce")
        if parsed.isna().any():
            fallback = pd.to_datetime(
                series.astype(str), utc=True, errors="coerce", format="ISO8601"
            )
            parsed = parsed.fillna(fallback)
        return parsed

    def _refresh_context_symbols(self, symbols: Iterable[str]) -> None:
        updated_symbols = set(self._context.symbols)
        for symbol in symbols:
            if symbol:
                updated_symbols.add(str(symbol).upper())
        self._context = FeatureContext(
            symbols=frozenset(updated_symbols),
            timeframes=self._timeframes,
            available_keys=frozenset(self._available_keys),
            determinism=self._determinism,
            _store=self._context._store,
        )

    def compute_feature_matrix(self, *, symbol: str, price_df: pd.DataFrame) -> pd.DataFrame:
        """Return a feature matrix aligned to the base timeframe index.

        The returned dataframe is indexed by the original ``timestamp`` index
        and contains one column per expanded feature key (``<alias>_<tf>``).
        Higher-timeframe indicators are forward-filled to the base index to
        simplify per-bar strategy evaluation.
        """

        if price_df.empty:
            return pd.DataFrame()

        symbol_key = str(symbol).upper()
        cache_key = self._cache_store.build_key(
            symbol=symbol_key,
            timeframe=self._default_timeframe,
            feature_version=self._feature_version,
            data_manifest_hash=self._data_manifest_hash,
        )
        cached = self._cache_store.get(cache_key)
        if cached is not None:
            self._refresh_context_symbols([symbol_key])
            return cached.copy() if hasattr(cached, "copy") else cached

        frame = price_df.copy()
        frame["timestamp"] = self._parse_timestamp_series(frame["timestamp"])
        frame = frame.dropna(subset=["timestamp"])
        if frame.empty:
            return pd.DataFrame()
        frame = frame.set_index("timestamp").sort_index()

        frames = {self._default_timeframe: frame}
        for tf in self._timeframes:
            if tf == self._default_timeframe:
                continue
            resampled = self._resample(frame, tf)
            if not resampled.empty:
                frames[tf] = resampled

        feature_columns: dict[str, pd.Series] = {}
        for timeframe, computed in self._compute_indicator_batches(frames):
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
        matrix = self._fill_missing_matrix(matrix)
        cached_matrix = matrix.copy()
        self._cache_store.set(
            cache_key,
            cached_matrix,
            metadata={
                "feature_version": self._feature_version,
                "seed": self._determinism.seed,
                "rows": len(matrix),
            },
        )
        # refresh context so manifest validation can see the symbol set
        self._refresh_context_symbols([symbol_key])
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
        pipeline_steps_path: str | Path | None = None,
        cache_store: FeatureCacheStore | None = None,
        cache_metrics_path: Path | None = None,
    ) -> FeaturePipeline:
        """Instantiate the pipeline from a YAML configuration file."""

        cfg_path = Path(path)
        with cfg_path.open("r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh.read())
        pipeline_steps = (
            cls._load_pipeline_steps(pipeline_steps_path) if pipeline_steps_path else None
        )
        return cls(
            config=config,
            feature_version=feature_version,
            data_manifest_hash=data_manifest_hash,
            seed=seed,
            pipeline_steps=pipeline_steps,
            cache_store=cache_store,
            cache_metrics_path=cache_metrics_path,
        )

    @classmethod
    def from_default_files(
        cls,
        *,
        feature_config_path: str | Path = Path("config") / "feature_pipeline.yaml",
        pipeline_steps_path: str | Path = Path("config") / "pipeline" / "m1_core.yaml",
        feature_version: str | None = None,
        data_manifest_hash: str | None = None,
        seed: int = 0,
        cache_store: FeatureCacheStore | None = None,
        cache_metrics_path: Path | None = None,
    ) -> FeaturePipeline:
        """Instantiate the pipeline from standard config paths."""

        return cls.from_config_file(
            feature_config_path,
            feature_version=feature_version,
            data_manifest_hash=data_manifest_hash,
            seed=seed,
            pipeline_steps_path=pipeline_steps_path,
            cache_store=cache_store,
            cache_metrics_path=cache_metrics_path,
        )

    @staticmethod
    def _load_pipeline_steps(path: str | Path | None) -> Sequence[Mapping[str, Any]] | None:
        if path is None:
            return None
        cfg_path = Path(path)
        if not cfg_path.exists():
            return None
        payload = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            return None
        steps = payload.get("steps")
        if not isinstance(steps, list):
            return None
        return steps

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
            forced_on = identifier in _ALWAYS_ON_INDICATORS
            if not raw_cfg.get("enabled", False) and not forced_on:
                continue
            timeframes = tuple(raw_cfg.get("timeframes", ()))
            if not timeframes:
                raise ValueError(f"Indicator '{identifier}' is enabled but defines no timeframes")

            if "output_key" in raw_cfg:
                output_keys: Mapping[str, str] = {"default": str(raw_cfg["output_key"])}
            elif "output_keys" in raw_cfg:
                output_keys = {
                    str(column): str(alias) for column, alias in raw_cfg["output_keys"].items()
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

        updated_symbols = set(self._context.symbols)
        latency_start = time.perf_counter()
        cpu_start = time.process_time()
        bars_processed = 0
        symbol_hint = None
        timeframe_hint = None
        if symbols:
            updated_symbols.update([str(symbol).upper() for symbol in symbols])
        if market_frame:
            bars = market_frame.get("bars") if isinstance(market_frame, Mapping) else None
            if isinstance(bars, list):
                bars_processed = len(bars)
            self._update_from_market_frame(market_frame)
            if isinstance(market_frame, Mapping):
                symbol = str(market_frame.get("symbol") or "").upper()
                symbol_hint = symbol or None
                timeframe_hint = str(market_frame.get("timeframe") or self._default_timeframe)
                if symbol:
                    updated_symbols.add(symbol)

        self._context = FeatureContext(
            symbols=frozenset(updated_symbols),
            timeframes=self._timeframes,
            available_keys=frozenset(self._available_keys),
            determinism=self._determinism,
            _store=self._store,
        )
        if market_frame and symbol_hint:
            self._emit_metrics(
                symbol=symbol_hint,
                timeframe=timeframe_hint or self._default_timeframe,
                bars=bars_processed,
                latency_ms=(time.perf_counter() - latency_start) * 1000,
                cpu_ms=(time.process_time() - cpu_start) * 1000,
            )
        return self._context

    def _emit_metrics(
        self,
        *,
        symbol: str,
        timeframe: str,
        bars: int,
        latency_ms: float,
        cpu_ms: float,
    ) -> None:
        payload = {
            "ts": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "symbol": symbol,
            "timeframe": timeframe,
            "bars": bars,
            "latency_ms": round(float(latency_ms), 3),
            "cpu_ms": round(float(cpu_ms), 3),
            "indicators": len(self._indicators),
        }
        try:
            self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
            with self._metrics_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        except OSError:
            return

    def _update_from_market_frame(self, market_frame: Mapping[str, Any]) -> None:
        symbol = str(market_frame.get("symbol") or "").upper()
        timeframe = str(market_frame.get("timeframe") or self._default_timeframe)
        bars = market_frame.get("bars") or []
        if not symbol or not bars:
            return
        df = self._bars_to_frame(bars)
        if df.empty:
            return

        frames: dict[str, pd.DataFrame] = {}
        frames[timeframe] = df
        if timeframe == self._default_timeframe:
            frames.update(self._resample_frames(df))

        for tf, frame_df in frames.items():
            self._store.setdefault(symbol, {}).setdefault(tf, {})
            if tf == self._default_timeframe:
                latest = frame_df.iloc[-1]
                self._store[symbol][tf].update(
                    {
                        f"open_{tf}": float(latest["open"]),
                        f"high_{tf}": float(latest["high"]),
                        f"low_{tf}": float(latest["low"]),
                        f"close_{tf}": float(latest["close"]),
                        f"volume_{tf}": float(latest.get("volume", 0.0)),
                    }
                )

        for timeframe, outputs in self._compute_indicator_batches(frames):
            for output_key, series in outputs.items():
                value = self._last_valid(series)
                if value is None:
                    continue
                self._store[symbol][timeframe][f"{output_key}_{timeframe}"] = value

    def _bars_to_frame(self, bars: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
        frame = pd.DataFrame(list(bars))
        if frame.empty:
            return frame
        ts_col = (
            "timestamp" if "timestamp" in frame.columns else "ts" if "ts" in frame.columns else None
        )
        if ts_col is None:
            return pd.DataFrame()
        frame = frame.rename(columns={ts_col: "timestamp"})
        frame["timestamp"] = self._parse_timestamp_series(frame["timestamp"])
        frame = frame.dropna(subset=["timestamp"])
        frame = frame.sort_values("timestamp")
        needed = {"open", "high", "low", "close"}
        if not needed.issubset(set(frame.columns)):
            return pd.DataFrame()
        if "volume" not in frame.columns:
            frame["volume"] = 0.0
        frame = frame.set_index("timestamp")
        if self._lookback_bars > 0 and len(frame) > self._lookback_bars:
            frame = frame.iloc[-self._lookback_bars :]
        return frame

    def _resample_frames(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        if not self._resample_enabled:
            return frames
        for tf in self._timeframes:
            if tf == self._default_timeframe:
                continue
            rule = _TIMEFRAME_RULES.get(tf)
            if not rule:
                continue
            resampled = df.resample(rule).agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            resampled = resampled.dropna(subset=["open", "high", "low", "close"])
            if not resampled.empty:
                frames[tf] = resampled
        return frames

    def _compute_indicator_batches(
        self, frames: Mapping[str, pd.DataFrame]
    ) -> list[tuple[str, Mapping[str, pd.Series]]]:
        """Compute indicator outputs for each timeframe, optionally in parallel."""

        batches: list[tuple[str, Mapping[str, pd.Series]]] = []
        if not self._indicators or not frames:
            return batches

        if self._max_workers <= 1 or len(self._indicators) == 1:
            for indicator in self._indicators.values():
                for timeframe, frame in frames.items():
                    if timeframe not in indicator.timeframes:
                        continue
                    batches.append((timeframe, self._compute_indicator(indicator, frame)))
            return batches

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_map = {}
            for indicator in self._indicators.values():
                for timeframe, frame in frames.items():
                    if timeframe not in indicator.timeframes:
                        continue
                    future = executor.submit(self._compute_indicator, indicator, frame)
                    future_map[future] = timeframe
            for future in as_completed(future_map):
                timeframe = future_map[future]
                outputs = future.result()
                batches.append((timeframe, outputs))
        return batches

    @staticmethod
    def _last_valid(series: pd.Series) -> object | None:
        if series.empty:
            return None
        clean = series.dropna()
        if clean.empty:
            return None
        value = clean.iloc[-1]
        try:
            return float(value)
        except (TypeError, ValueError):
            return value

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
    def pipeline_steps(self) -> tuple[Mapping[str, Any], ...]:
        """Expose pipeline step definitions loaded from config."""

        return tuple(self._pipeline_steps)

    @property
    def context(self) -> FeatureContext:
        """Return the latest :class:`FeatureContext` snapshot."""

        return self._context
