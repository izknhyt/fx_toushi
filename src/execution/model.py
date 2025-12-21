"""Protocols and lightweight dataclasses for execution modelling.

The production implementation will evolve into a deterministic execution
model that applies human delay, spread state, and broker rules to raw
strategy signals.  The scaffolding here mirrors the API contracts from
``detailed_design_fx_signal_tool_v1.md`` so that other packages and tests
can type-check against them while the heavy lifting is developed in
future packets.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable, cast

from typing_extensions import Literal

EntryMode = Literal["market", "marketable_limit", "limit_requote"]
"""Enumeration of strategy-requested entry modes from the design contract."""

FillStyle = Literal["ioc", "fok", "gtd"]
"""Abstract fill execution semantics surfaced to downstream components."""

FillPolicy = Literal["ioc", "fok", "gtd", "day"]
"""Policy hints consumed by the order router and ticket builder.

``"fok"`` and ``"gtd"`` align with :data:`FillStyle` to carry venue specific
semantics alongside the higher level execution hints.
"""


@dataclass(slots=True, frozen=True)
class ExecutionAdjustments:
    """Deterministic adjustments derived from the execution model.

    The fields intentionally capture the data that downstream components
    (risk manager, position sizer, ticket builder) consume.  They mirror
    the detailed design but default to ``None``/sentinel values so the
    scaffolding can be instantiated in tests without requiring market
    data.
    """

    expected_entry: float | None
    """Price the strategy should expect after delay/slippage corrections."""

    expected_slippage: float | None
    """Projected slippage in pips or price units depending on the venue."""

    ttl_seconds: int
    """Good-until time in seconds for IOC/limit style routing."""

    fill_style: FillStyle
    """High level fill semantic (IOC, GTD, etc.)."""

    fill_policy: FillPolicy | None = None
    """Optional routing hint for downstream adapters."""

    mode_label: str | None = None
    """Human readable label surfaced on tickets and dashboards."""

    drift_guard_r: float | None = None
    """Optional drift guard threshold expressed in risk R units."""


class ExecutionError(RuntimeError):
    """Base error for execution model scaffolding."""


class ExecutionConfigError(ExecutionError):
    """Raised when execution configuration validation fails."""


class ExecutionRuleViolation(ExecutionError):
    """Raised when a signal violates execution guardrails."""


class ExecutionModelInputError(ExecutionError):
    """Raised when required inputs for the execution model are missing."""


@runtime_checkable
class ExecutionModelProtocol(Protocol):
    """Protocol describing the public API of the execution model."""

    def apply(
        self,
        signal: Any,
        market_snapshot: Mapping[str, Any],
        *,
        spread_state: Any,
        mode_context: Mapping[str, Any] | None = None,
    ) -> ExecutionAdjustments:
        """Apply execution adjustments to a raw strategy signal."""

    def validate_config(self, config: Mapping[str, Any]) -> None:
        """Validate execution model configuration data."""

    def apply_human_delay(self, *, seed: int) -> float:
        """Return the simulated human delay in seconds for deterministic tests."""


class DeterministicExecutionModel(ExecutionModelProtocol):
    """Deterministic baseline execution model used across test scaffolding.

    The implementation intentionally keeps the logic straightforward while
    mirroring the configuration knobs surfaced in ``execution_model.yaml``.
    It translates spread states into entry mode badges/TTL targets and applies
    human delay sampling using :class:`ModeContext` deterministic seeds so that
    Backtest/Paper/Live runs share identical outcomes.
    """

    _MODE_LABELS: Mapping[str, str] = MappingProxyType(
        {
            "market": "Market (IOC)",
            "marketable_limit": "Marketable Limit",
            "limit_requote": "Limit (Requote)",
        }
    )

    _SPREAD_TTL_BUCKET: Mapping[str, str] = MappingProxyType(
        {
            "normal": "base",
            "watch": "fast_path",
            "cooldown": "slow_path",
        }
    )

    def __init__(self, config: Mapping[str, Any], *, metrics_path: Path | None = None) -> None:
        self._config = config
        self._delay_stats_cache: dict[int, Mapping[str, float]] = {}
        env_path = os.getenv("EXEC_DETERMINISM_METRICS")
        if env_path is not None and env_path.strip() == "0":
            self._metrics_path = None
        else:
            self._metrics_path = (
                Path(env_path)
                if env_path
                else (Path(metrics_path) if metrics_path is not None else Path("metrics") / "execution_determinism.jsonl")
            )
        self.validate_config(config)

    # ------------------------------------------------------------------
    # public API
    def apply(
        self,
        signal: Any,
        market_snapshot: Mapping[str, Any],
        *,
        spread_state: Any,
        mode_context: Mapping[str, Any] | Any | None = None,
    ) -> ExecutionAdjustments:
        state = self._resolve_spread_state(spread_state)
        if state == "halt":
            raise ExecutionRuleViolation("Spread halt prohibits order routing")
        if state is None:
            raise ExecutionModelInputError("Spread state is required for execution")

        mode = self._extract_value(mode_context, "mode", default="backtest")
        deterministic_seed = int(self._extract_value(mode_context, "deterministic_seed", default=0))
        symbol = getattr(signal, "symbol", None)
        latency_status = self._extract_value(mode_context, "latency_data_status", default="ok")
        slippage_status = self._extract_value(mode_context, "slippage_data_status", default="ok")
        observed_slippage = self._resolve_observed_slippage(market_snapshot, mode_context)
        rollover_pips = self._resolve_rollover_cost(market_snapshot, mode_context)
        observed_candidates = [
            observed_slippage,
            market_snapshot.get("observed_slippage_pips"),
            market_snapshot.get("slippage_pips"),
            self._extract_value(mode_context, "observed_slippage_pips", default=None),
        ]
        observed_values: list[float] = []
        for val in observed_candidates:
            try:
                if val is not None:
                    observed_values.append(abs(float(val)))
            except (TypeError, ValueError):
                continue
        observed_max = max(observed_values) if observed_values else 0.0
        spread_pips = self._extract_spread_pips(signal, market_snapshot)

        entry_mode = self._resolve_entry_mode(signal, state)
        mode_label = self._MODE_LABELS.get(entry_mode, entry_mode)
        entry_config = self._lookup_entry_mode(entry_mode)
        self._enforce_spread(entry_config, spread_pips)
        fill_style, fill_policy = self._resolve_fill_style(entry_config)
        direction = getattr(signal, "direction", "long")

        delay_stats = self._resolve_delay_stats(mode=mode, symbol=symbol)
        seed_offset = int(delay_stats.get("seed_offset", 0))
        delay_seed = deterministic_seed ^ seed_offset
        self._delay_stats_cache[delay_seed] = delay_stats
        try:
            human_delay = self.apply_human_delay(seed=delay_seed)
        finally:
            self._delay_stats_cache.pop(delay_seed, None)

        ttl_bucket_key = self._SPREAD_TTL_BUCKET.get(state, "base")
        ttl_buffer = self._resolve_ttl_buffer(ttl_bucket_key)
        ttl_seconds = int(round(ttl_buffer + human_delay))

        expected_entry = self._resolve_expected_entry(signal, market_snapshot)
        expected_slippage = self._resolve_expected_slippage(state)
        expected_slippage = self._apply_spread_to_slippage(
            expected_slippage,
            spread_pips,
            entry_config,
            allow_exceed=observed_max > 0,
        )
        expected_slippage = self._apply_observed_slippage(expected_slippage, observed_slippage)
        max_candidates = [expected_slippage or 0.0, observed_max]
        if rollover_pips is not None:
            try:
                max_candidates.append(abs(float(rollover_pips)))
            except (TypeError, ValueError):
                pass
        expected_slippage = max(max_candidates)
        expected_slippage = self._apply_rollover_cost(expected_slippage, rollover_pips, direction=direction)

        ttl_seconds = self._apply_ttl_fallback(ttl_seconds, latency_status)
        expected_slippage = self._apply_slippage_fallback(expected_slippage, slippage_status)

        adjustments = ExecutionAdjustments(
            expected_entry=expected_entry,
            expected_slippage=expected_slippage,
            ttl_seconds=ttl_seconds,
            fill_style=fill_style,
            fill_policy=fill_policy,
            mode_label=mode_label,
        )
        self._record_metrics(
            signal=signal,
            spread_state=state,
            seed=deterministic_seed,
            ttl_seconds=ttl_seconds,
            human_delay=human_delay,
            expected_slippage=expected_slippage,
            observed_slippage=observed_slippage,
            rollover_pips=rollover_pips,
            latency_status=latency_status,
            slippage_status=slippage_status,
            mode=mode,
            determinism=self._extract_value(mode_context, "determinism", default=None),
        )
        return adjustments

    def validate_config(self, config: Mapping[str, Any]) -> None:
        if not isinstance(config, Mapping):
            raise ExecutionConfigError("Execution model config must be a mapping")

        schema_version = config.get("schema_version")
        if schema_version != "execution.model.v1":
            raise ExecutionConfigError(
                "Execution model config must declare schema_version 'execution.model.v1'"
            )

        defaults = config.get("defaults")
        if not isinstance(defaults, Mapping):
            raise ExecutionConfigError("Execution model config missing defaults mapping")

        delay_defaults = defaults.get("human_delay_seconds")
        if not isinstance(delay_defaults, Mapping):
            raise ExecutionConfigError("defaults.human_delay_seconds must be provided")
        for mode_key in ("backtest", "paper", "live"):
            stats = delay_defaults.get(mode_key)
            if not isinstance(stats, Mapping):
                raise ExecutionConfigError(f"human_delay_seconds missing '{mode_key}' distribution")
            self._validate_delay_stats(stats, context=f"human_delay_seconds.{mode_key}")

        ttl_defaults = defaults.get("ttl_seconds")
        if not isinstance(ttl_defaults, Mapping):
            raise ExecutionConfigError("defaults.ttl_seconds must be provided")
        for required_bucket in ("base", "fast_path", "slow_path"):
            value = ttl_defaults.get(required_bucket)
            if not isinstance(value, (int, float)):
                raise ExecutionConfigError(
                    f"ttl_seconds bucket '{required_bucket}' must be a numeric value"
                )
            if value < 0:
                raise ExecutionConfigError("ttl_seconds buckets must be non-negative")
        fallbacks = defaults.get("fallbacks", {})
        if fallbacks:
            for key in ("slippage_fallback_pips", "ttl_fallback_sec"):
                value = fallbacks.get(key)
                if not isinstance(value, (int, float)):
                    raise ExecutionConfigError(f"defaults.fallbacks.{key} must be numeric when provided")

        entry_defaults = defaults.get("entry_modes")
        if not isinstance(entry_defaults, Mapping):
            raise ExecutionConfigError("defaults.entry_modes must be provided")
        for entry_mode in ("market", "marketable_limit", "limit_requote"):
            if entry_mode not in entry_defaults:
                raise ExecutionConfigError(
                    f"entry_modes missing required configuration for '{entry_mode}'"
                )

    def apply_human_delay(self, *, seed: int) -> float:
        stats = self._delay_stats_cache.get(seed)
        if stats is None:
            defaults = self._config.get("defaults", {})
            delay_defaults = {}
            if isinstance(defaults, Mapping):
                delay_defaults = defaults.get("human_delay_seconds", {})
            stats = delay_defaults.get("backtest", {})
        minimum = float(stats.get("min", 0.0))
        mode = float(stats.get("p50", minimum))
        maximum = float(stats.get("p95", max(mode, minimum)))
        if maximum < minimum:
            maximum = minimum
        rng = random.Random(seed)
        # Deterministic uniform draw; `mode` retained for compatibility but unused.
        return rng.uniform(minimum, maximum)

    # ------------------------------------------------------------------
    # helpers
    def _extract_value(self, source: Mapping[str, Any] | Any | None, key: str, *, default: Any) -> Any:
        if source is None:
            return default
        if isinstance(source, Mapping):
            return source.get(key, default)
        return getattr(source, key, default)

    def _safe_float(self, value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _resolve_spread_state(self, spread_state: Any) -> str | None:
        if spread_state is None:
            return None
        if isinstance(spread_state, Mapping):
            value = spread_state.get("state")
        else:
            value = getattr(spread_state, "state", spread_state)
        if value is None:
            return None
        return str(value)

    def _resolve_entry_mode(self, signal: Any, spread_state: str) -> str:
        default_mode = getattr(signal, "entry_mode", None) or "marketable_limit"
        entry_mode = str(default_mode)
        if spread_state == "watch":
            return "market"
        if spread_state == "cooldown":
            return "limit_requote"
        return entry_mode

    def _lookup_entry_mode(self, entry_mode: str) -> Mapping[str, Any]:
        defaults = self._config.get("defaults", {})
        if isinstance(defaults, Mapping):
            entry_modes = defaults.get("entry_modes", {})
            if isinstance(entry_modes, Mapping):
                config = entry_modes.get(entry_mode)
                if isinstance(config, Mapping):
                    return config
        raise ExecutionConfigError(f"Entry mode '{entry_mode}' not configured")

    def _resolve_fill_style(self, entry_config: Mapping[str, Any]) -> tuple[FillStyle, FillPolicy | None]:
        fill_style = entry_config.get("fill_style")
        if fill_style not in {"ioc", "fok", "gtd"}:
            if entry_config.get("allow_ioc"):
                fill_style = "ioc"
            elif entry_config.get("allow_fok"):
                fill_style = "fok"
            else:
                fill_style = "gtd"
        fill_policy: FillPolicy | None
        if fill_style == "gtd" and entry_config.get("allow_day"):
            fill_policy = "day"
        else:
            fill_policy = cast(FillPolicy, fill_style) if fill_style in {"ioc", "fok", "gtd"} else None
        return cast(FillStyle, fill_style), fill_policy

    def _resolve_delay_stats(self, *, mode: str, symbol: Any) -> Mapping[str, float]:
        defaults = self._config.get("defaults", {})
        delay_defaults = {}
        if isinstance(defaults, Mapping):
            delay_defaults = defaults.get("human_delay_seconds", {})
        stats: Mapping[str, float] | None = None
        if isinstance(symbol, str):
            symbol_overrides = self._config.get("symbols", {})
            if isinstance(symbol_overrides, Mapping):
                symbol_config = symbol_overrides.get(symbol)
                if isinstance(symbol_config, Mapping):
                    symbol_delay = symbol_config.get("human_delay_seconds")
                    if isinstance(symbol_delay, Mapping):
                        stats = symbol_delay.get(mode)
        if stats is None and isinstance(delay_defaults, Mapping):
            stats = delay_defaults.get(mode)
        if not isinstance(stats, Mapping):
            raise ExecutionConfigError(f"Human delay distribution missing for mode '{mode}'")
        return stats

    def _resolve_ttl_buffer(self, bucket: str) -> float:
        defaults = self._config.get("defaults", {})
        ttl_defaults = {}
        if isinstance(defaults, Mapping):
            ttl_defaults = defaults.get("ttl_seconds", {})
        if isinstance(ttl_defaults, Mapping) and bucket in ttl_defaults:
            value = ttl_defaults[bucket]
        else:
            value = ttl_defaults.get("base", 0)
        return float(value)

    def _apply_ttl_fallback(self, ttl_seconds: int, latency_status: str) -> int:
        fallbacks = self._config.get("defaults", {}).get("fallbacks", {})
        extra = 0.0
        if not isinstance(fallbacks, Mapping):
            return ttl_seconds
        if latency_status in {"degraded", "halt_recommended"}:
            extra = float(fallbacks.get("ttl_fallback_sec", 0.0))
        ttl = ttl_seconds + extra
        if latency_status == "halt_recommended":
            ttl += extra  # double bump when hard degraded
        return int(round(ttl))

    def _apply_slippage_fallback(self, expected_slippage: float | None, slippage_status: str) -> float | None:
        fallbacks = self._config.get("defaults", {}).get("fallbacks", {})
        if not isinstance(fallbacks, Mapping):
            return expected_slippage
        fallback_value = fallbacks.get("slippage_fallback_pips")
        if fallback_value is None:
            return expected_slippage
        try:
            fallback = float(fallback_value)
        except (TypeError, ValueError):
            return expected_slippage
        if slippage_status in {"degraded", "halt_recommended"}:
            if expected_slippage is None:
                return fallback
            return max(expected_slippage, fallback)
        return expected_slippage

    def _resolve_expected_entry(self, signal: Any, market_snapshot: Mapping[str, Any]) -> float | None:
        for attribute in ("expected_entry", "entry_price", "price", "mid"):
            value = getattr(signal, attribute, None)
            if value is not None:
                return float(value)
        for key in ("expected_entry", "entry_price", "price", "mid"):
            value = market_snapshot.get(key)
            if value is not None:
                return float(value)
        return None

    def _resolve_expected_slippage(self, spread_state: str) -> float | None:
        defaults = self._config.get("defaults", {})
        if not isinstance(defaults, Mapping):
            return None
        slippage_defaults = defaults.get("slippage_pips")
        if not isinstance(slippage_defaults, Mapping):
            return None
        if spread_state == "watch":
            bucket_name = "volatile"
            percentile = "p90"
        elif spread_state == "cooldown":
            bucket_name = "base"
            percentile = "p90"
        else:
            bucket_name = "base"
            percentile = "p50"
        bucket = slippage_defaults.get(bucket_name)
        if not isinstance(bucket, Mapping):
            bucket = next((cfg for cfg in slippage_defaults.values() if isinstance(cfg, Mapping)), None)
        if not bucket:
            return None
        value = bucket.get(percentile)
        if value is None:
            fallback = bucket.get("p50")
            if fallback is None:
                return None
            value = fallback
        return float(value)

    def _apply_spread_to_slippage(self, expected_slippage: float | None, spread_pips: float | None, entry_config: Mapping[str, Any], *, allow_exceed: bool = False) -> float | None:
        if spread_pips is None:
            return expected_slippage
        value = expected_slippage or 0.0
        value = max(value, spread_pips)
        max_slippage = entry_config.get("max_slippage_pips")
        if max_slippage is not None:
            try:
                cap = float(max_slippage)
            except (TypeError, ValueError):
                return value
            if not allow_exceed:
                value = min(value, cap)
        return value

    def _apply_observed_slippage(self, expected_slippage: float | None, observed_slippage: float | None) -> float | None:
        if observed_slippage is None:
            return expected_slippage
        value = expected_slippage or 0.0
        return max(value, observed_slippage)

    def _apply_rollover_cost(self, expected_slippage: float | None, rollover_pips: float | None, *, direction: str = "long") -> float | None:
        if rollover_pips is None:
            return expected_slippage
        value = expected_slippage or 0.0
        try:
            adj = abs(float(rollover_pips))
        except (TypeError, ValueError):
            return value
        return max(value, adj)

    def _enforce_spread(self, entry_config: Mapping[str, Any], spread_pips: float | None) -> None:
        if spread_pips is None:
            return
        max_spread = entry_config.get("max_spread_pips")
        if max_spread is None:
            return
        try:
            max_spread_val = float(max_spread)
        except (TypeError, ValueError):
            return
        if spread_pips > max_spread_val:
            raise ExecutionRuleViolation(f"Spread {spread_pips} exceeds max_spread_pips {max_spread_val}")

    def _extract_spread_pips(self, signal: Any, market_snapshot: Mapping[str, Any]) -> float | None:
        value = getattr(signal, "spread_pips", None)
        if value is None:
            value = market_snapshot.get("spread_pips")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _resolve_observed_slippage(self, market_snapshot: Mapping[str, Any], mode_context: Mapping[str, Any] | Any | None) -> float | None:
        for key in ("observed_slippage_pips", "slippage_pips"):
            value = market_snapshot.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        ctx_value = self._extract_value(mode_context, "observed_slippage_pips", default=None)
        if ctx_value is not None:
            try:
                return float(ctx_value)
            except (TypeError, ValueError):
                pass
        log_entry = market_snapshot.get("slippage_log")
        if isinstance(log_entry, Mapping):
            for key in ("avg_pips", "mean_pips", "p95", "avg"):
                value = log_entry.get(key)
                if value is None:
                    continue
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        spread_obs = market_snapshot.get("spread_observations") or market_snapshot.get("spread_history")
        if spread_obs:
            try:
                values = [abs(float(v)) for v in spread_obs if v is not None]
                if values:
                    return max(values)
            except (TypeError, ValueError):
                pass
        samples = getattr(mode_context, "slippage_samples", None) if mode_context else None
        if samples and hasattr(samples, "__iter__"):
            try:
                values = [float(v) for v in samples]
                if values:
                    return sum(values) / len(values)
            except (TypeError, ValueError):
                return None
        return None

    def _resolve_rollover_cost(self, market_snapshot: Mapping[str, Any], mode_context: Mapping[str, Any] | Any | None) -> float | None:
        for key in ("rollover_pips", "swap_pips"):
            value = market_snapshot.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        ctx_value = self._extract_value(mode_context, "rollover_pips", default=None)
        if ctx_value is not None:
            try:
                return float(ctx_value)
            except (TypeError, ValueError):
                pass
        log_entry = market_snapshot.get("rollover_log")
        if isinstance(log_entry, Mapping):
            for key in ("last_pips", "avg_pips", "p95", "max_pips"):
                value = log_entry.get(key)
                if value is None:
                    continue
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return None

    def _record_metrics(
        self,
        *,
        signal: Any,
        spread_state: str,
        seed: int,
        ttl_seconds: int,
        human_delay: float,
        expected_slippage: float | None,
        observed_slippage: float | None,
        rollover_pips: float | None,
        latency_status: str,
        slippage_status: str,
        mode: str,
        determinism: Any = None,
    ) -> None:
        if self._metrics_path is None:
            return
        try:
            self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
            feature_version = getattr(determinism, "feature_version", None)
            data_manifest_hash = getattr(determinism, "data_manifest_hash", None)
            determinism_hash = getattr(determinism, "determinism_hash", None)
            payload = {
                "event": "execution.determinism",
                "strategy_id": getattr(signal, "strategy_id", None),
                "symbol": getattr(signal, "symbol", None),
                "spread_state": spread_state,
                "seed": seed,
                "mode": mode,
                "ttl_seconds": ttl_seconds,
                "human_delay_ms": int(round(human_delay * 1000)),
                "expected_slippage_pips": expected_slippage,
                "observed_slippage_pips": observed_slippage,
                "rollover_pips": rollover_pips,
                "latency_status": latency_status,
                "slippage_status": slippage_status,
                "feature_version": feature_version,
                "data_manifest_hash": data_manifest_hash,
                "determinism_hash": determinism_hash,
                "ts": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            }
            with self._metrics_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False))
                handle.write("\n")
        except OSError:
            pass

    def _validate_delay_stats(self, stats: Mapping[str, Any], *, context: str) -> None:
        for key in ("min", "p50", "p95"):
            value = stats.get(key)
            if not isinstance(value, (int, float)):
                raise ExecutionConfigError(f"{context} must define numeric '{key}'")
            if value < 0:
                raise ExecutionConfigError(f"{context}.{key} must be non-negative")
        minimum = float(stats["min"])
        median = float(stats["p50"])
        tail = float(stats["p95"])
        if not (minimum <= median <= tail):
            raise ExecutionConfigError(
                f"{context} must satisfy min <= p50 <= p95 (got {minimum}, {median}, {tail})"
            )


__all__ = [
    "EntryMode",
    "ExecutionAdjustments",
    "ExecutionError",
    "ExecutionConfigError",
    "ExecutionModelInputError",
    "ExecutionModelProtocol",
    "ExecutionRuleViolation",
    "DeterministicExecutionModel",
    "FillPolicy",
    "FillStyle",
]
