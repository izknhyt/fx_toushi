"""Lightweight paper-trading PoC simulator.

This module stitches together the feature pipeline, strategy engine, and a
deterministic trade loop so we can run a one-month style paper simulation
without broker connectivity.  It mirrors the PoC scope outlined in
`detailed_design_fx_signal_tool_v1.md` §0.6.14 and emits metrics compatible
with the PoC templates under `reports/backtest/`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml

from src.features.pipeline import FeaturePipeline
from src.strategies.donchian import (
    DonchianBreakoutLongOnlyStrategy,
    DonchianBreakoutStrategy,
    DonchianBreakoutUpperOnlyStrategy,
)
from src.strategies.ma_rsi import MovingAverageRsiStrategy
from src.strategies.us_session_momentum import UsSessionTrendPullbackStrategy
from src.strategies.allocation import StrategyAllocationPolicy
from src.strategies.registry import StrategyEngine, StrategyManifest

DEFAULT_DATA_MANIFEST = Path("reports") / "data_manifest.json"
DEFAULT_STRATEGY_MANIFEST = Path("config") / "strategy_manifest.yaml"
DEFAULT_FEATURE_CONFIG = Path("config") / "feature_pipeline.yaml"
DEFAULT_RISK_POLICY = Path("config") / "risk_policy.yaml"
DEFAULT_RETURNS_EXPORT = Path("reports") / "performance" / "paper" / "returns.parquet"
DEFAULT_EQUITY_EXPORT = Path("reports") / "performance" / "paper" / "equity.parquet"


@dataclass(slots=True)
class StreakRules:
    """Streak-based risk adjustments."""

    loss_threshold: int = 3
    loss_risk_pct: float = 0.5
    win_threshold: int = 2
    win_step_pct: float = 0.1
    win_cap_pct: float = 1.0
    reset_on_loss: bool = True


@dataclass(slots=True)
class StrategyRiskLimits:
    """Per-strategy risk overrides."""

    per_trade_pct: float
    r_eff_soft: float | None = None
    r_eff_hard: float | None = None
    max_concurrent_overall: int | None = None
    max_concurrent_bucket: int | None = None


@dataclass(slots=True)
class RiskProfileSettings:
    base_equity: float
    base_per_trade_pct: float
    streak: StreakRules
    per_strategy_limits: dict[str, StrategyRiskLimits]
    total_risk_soft_pct: float | None = None
    total_risk_hard_pct: float | None = None
    bucket_risk_cap_pct: float | None = None
    r_eff_soft: float | None = None
    r_eff_hard: float | None = None
    corr_group_risk_cap_pct: float | None = None


@dataclass(slots=True)
class TradeRecord:
    """Captured trade lifecycle for the PoC simulator."""

    strategy_id: str | None
    opened_at: datetime
    closed_at: datetime
    symbol: str
    direction: str
    entry: float
    exit: float
    stop: float
    target: float
    r_multiple: float
    pnl: float
    breakout: str | None = None
    level: float | None = None
    buffer: float | None = None
    breakout_width: float | None = None
    quality_score: float | None = None
    filter_flags: Mapping[str, bool] | None = None
    trend_value: float | None = None
    atr_value: float | None = None
    spread_used: float | None = None
    slippage_used: float | None = None

    def as_dict(self) -> Mapping[str, Any]:
        payload = asdict(self)
        payload["opened_at"] = self.opened_at.isoformat()
        payload["closed_at"] = self.closed_at.isoformat()
        return payload


@dataclass(slots=True)
class PocResult:
    """Aggregated PoC outcome and supporting trades."""

    metrics: Mapping[str, float]
    trades: list[TradeRecord]
    dataset_path: str | list[str]
    dataset_hash: str | list[str]
    window: Mapping[str, str | None]
    seed_used: int = 0
    returns: list[float] | None = None
    equity_curve: list[float] | None = None

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "metrics": dict(self.metrics),
            "trades": [trade.as_dict() for trade in self.trades],
            "dataset_path": self.dataset_path,
            "dataset_hash": self.dataset_hash,
            "window": self.window,
            "seed_used": self.seed_used,
            "returns": list(self.returns) if self.returns is not None else None,
            "equity_curve": list(self.equity_curve) if self.equity_curve is not None else None,
        }


def _load_data_manifest(path: Path, strategy: str) -> Mapping[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entry = manifest.get("strategies", {}).get(strategy)
    if not entry:
        fallback = {
            "m1_baseline_donchian_long_only": "m1_baseline_donchian",
            "m1_baseline_donchian_upper_only": "m1_baseline_donchian",
            "m1_us_session_trend_pullback": "m1_baseline_ma_rsi",
        }.get(strategy)
        if fallback:
            entry = manifest.get("strategies", {}).get(fallback)
    if not entry:
        raise KeyError(f"Strategy '{strategy}' missing in {path}")
    if "dataset_path" not in entry or "dataset_sha256" not in entry:
        raise ValueError(f"Strategy '{strategy}' manifest entry missing dataset information")
    return entry


def _restrict_manifest_to_strategy(manifest: StrategyManifest, strategy_id: str) -> None:
    for sid, entry in manifest.strategies.items():
        entry.enabled = sid == strategy_id


def _resolve_manifest_entries(
    manifest: StrategyManifest, strategy: str | None
) -> tuple[dict[str, Any], list[tuple[str, Any]]]:
    if strategy:
        selected = manifest.strategies[strategy]
        _restrict_manifest_to_strategy(manifest, strategy)
        return {strategy: selected}, [(strategy, selected)]

    enabled = list(manifest.enabled_strategies())
    if not enabled:
        raise ValueError("No enabled strategies found in strategy manifest")
    return {sid: entry for sid, entry in enabled}, enabled


def _load_risk_policy(risk_policy_path: Path, profile: str) -> RiskProfileSettings:
    policy = yaml.safe_load(risk_policy_path.read_text(encoding="utf-8"))
    base_capital = float(policy.get("metadata", {}).get("base_capital_jpy", 12_000_000))
    profiles = policy.get("profiles", {})
    selected = profiles.get(profile, {})
    limits = selected.get("risk_limits", {})
    total_risk_cfg = limits.get("total_open_risk_pct", {})
    bucket_risk_cap_pct = limits.get("bucket_open_risk_pct")
    r_eff_soft = float(limits.get("exposure_r_eff_soft_stop", 0)) or None
    r_eff_hard = float(limits.get("exposure_r_eff_hard_stop", 0)) or None
    corr_group_risk_cap_pct = limits.get("correlation_group_risk_pct")

    base_pct = float(limits.get("per_trade_risk_pct", 0.5))
    streak_cfg = limits.get("streak_adjustments", {})
    losing_cfg = streak_cfg.get("losing", {})
    winning_cfg = streak_cfg.get("winning", {})
    streak = StreakRules(
        loss_threshold=int(losing_cfg.get("threshold_trades", 3)),
        loss_risk_pct=float(losing_cfg.get("per_trade_risk_pct", 0.5)),
        win_threshold=int(winning_cfg.get("threshold_trades", 2)),
        win_step_pct=float(winning_cfg.get("step_increment_pct", 0.1)),
        win_cap_pct=float(winning_cfg.get("cap_per_trade_pct", 1.0)),
        reset_on_loss=bool(winning_cfg.get("reset_on_loss", True)),
    )

    per_strategy_limits: dict[str, StrategyRiskLimits] = {}
    for strategy_id, raw in limits.get("per_strategy_limits", {}).items():
        per_strategy_limits[str(strategy_id)] = StrategyRiskLimits(
            per_trade_pct=float(raw.get("per_trade_risk_pct", base_pct)),
            r_eff_soft=float(
                raw.get("exposure_r_eff_soft_stop", limits.get("exposure_r_eff_soft_stop", 2.0))
            ),
            r_eff_hard=float(
                raw.get("exposure_r_eff_hard_stop", limits.get("exposure_r_eff_hard_stop", 2.5))
            ),
            max_concurrent_overall=int(raw.get("max_concurrent_positions", {}).get("overall", 1))
            if isinstance(raw.get("max_concurrent_positions"), dict)
            else None,
            max_concurrent_bucket=int(
                raw.get("max_concurrent_positions", {}).get("per_currency_bucket", 1)
            )
            if isinstance(raw.get("max_concurrent_positions"), dict)
            else None,
        )

    return RiskProfileSettings(
        base_equity=base_capital,
        base_per_trade_pct=base_pct,
        streak=streak,
        per_strategy_limits=per_strategy_limits,
        total_risk_soft_pct=float(total_risk_cfg.get("soft", 0)) or None,
        total_risk_hard_pct=float(total_risk_cfg.get("hard", 0)) or None,
        bucket_risk_cap_pct=float(bucket_risk_cap_pct or 0) or None,
        r_eff_soft=r_eff_soft,
        r_eff_hard=r_eff_hard,
        corr_group_risk_cap_pct=float(corr_group_risk_cap_pct or 0) or None,
    )


def _build_gate_state(symbols: Iterable[str]) -> SimpleNamespace:
    """Construct a minimal GateState compatible object."""

    news = SimpleNamespace(blocked=False, reason=None, release_ts=None)
    calendar = SimpleNamespace(blocked=False, holiday_block=False, reason=None)
    spread = SimpleNamespace(state="normal", reason=None, cooldown_eta=None)
    per_symbol = {
        symbol: SimpleNamespace(news=news, calendar=calendar, spread=spread) for symbol in symbols
    }
    market = SimpleNamespace(
        news=news,
        calendar=calendar,
        spread=spread,
        latency_data_status="ok",
        slippage_data_status="ok",
        profit_readiness_status="ok",
        per_symbol=per_symbol,
    )
    risk = SimpleNamespace(reduce_only=False, reduce_only_reason=None)
    human = SimpleNamespace(
        double_entry_required=False,
        required_roles=(),
        acknowledged_roles=(),
        ack_deadline=None,
        manual_comment_required=False,
        comment_min_length=0,
    )
    return SimpleNamespace(market=market, risk=risk, human=human, schema_version="poc")


def _feature_context_for_row(
    pipeline: FeaturePipeline, symbols: Iterable[str], row: pd.Series
) -> tuple[Any, SimpleNamespace]:
    """Materialise a single-bar FeatureContext store."""

    symbols = list(symbols)
    symbol = symbols[0]
    store: dict[str, dict[str, dict[str, Any]]] = {symbol: {}}
    for feature_name in pipeline.available_keys:
        value = row.get(feature_name)
        if pd.isna(value):
            continue
        timeframe = feature_name.split("_")[-1]
        store[symbol].setdefault(timeframe, {})[feature_name] = value

    context = pipeline.update(symbols=symbols)
    context = context.__class__(
        symbols=context.symbols,
        timeframes=context.timeframes,
        available_keys=context.available_keys,
        _store=store,
    )
    clock = SimpleNamespace(now=row.name.to_pydatetime(), timeframe="5m")
    return context, clock


def _spread_for(symbol: str, ts: pd.Timestamp, base_spread: float) -> float:
    """Simple time-of-day and symbol-based spread model."""

    hour = getattr(ts, "hour", None)
    session_mult = 1.15 if hour is not None and (hour < 6 or hour >= 22) else 1.0
    symbol_mult = {
        "USDJPY": 1.0,
        "EURUSD": 1.0,
        "GBPUSD": 1.05,
        "EURJPY": 1.05,
        "AUDUSD": 1.05,
    }.get(symbol.upper(), 1.1)
    return base_spread * session_mult * symbol_mult


def _slippage_for(symbol: str, ts: pd.Timestamp, mean: float, std: float) -> float:
    """Sample slippage with symbol/time multipliers."""

    hour = getattr(ts, "hour", None)
    session_mult = 1.15 if hour is not None and (hour < 6 or hour >= 22) else 1.0
    symbol_mult = {
        "USDJPY": 1.0,
        "EURUSD": 1.0,
        "GBPUSD": 1.05,
        "EURJPY": 1.05,
        "AUDUSD": 1.05,
    }.get(symbol.upper(), 1.1)
    mu = mean * session_mult * symbol_mult
    sigma = std * session_mult * symbol_mult
    if sigma <= 0:
        return mu
    return float(np.random.normal(mu, sigma))


def _exit_with_cost(*, price: float, direction: str, spread: float, slippage: float) -> float:
    """Apply adverse exit costs for the position direction."""

    if direction == "long":
        return price - spread - slippage
    return price + spread + slippage


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except Exception:
        return None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    to_pydatetime = getattr(value, "to_pydatetime", None)
    if callable(to_pydatetime):
        try:
            converted = to_pydatetime()
        except Exception:
            return None
        if isinstance(converted, datetime):
            return converted
    return None


def _weekdays_from_value(value: Any) -> frozenset[int]:
    token_map = {
        "mon": 0,
        "monday": 0,
        "tue": 1,
        "tuesday": 1,
        "wed": 2,
        "wednesday": 2,
        "thu": 3,
        "thursday": 3,
        "fri": 4,
        "friday": 4,
        "sat": 5,
        "saturday": 5,
        "sun": 6,
        "sunday": 6,
    }
    if value is None:
        return frozenset()
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    else:
        items = [value]
    weekdays: list[int] = []
    for item in items:
        if isinstance(item, (int, float)):
            weekday = int(item)
            if 0 <= weekday <= 6:
                weekdays.append(weekday)
            continue
        token = str(item).strip().lower()
        if token in token_map:
            weekdays.append(token_map[token])
    return frozenset(weekdays)


def _hours_from_value(value: Any) -> frozenset[int]:
    if value is None:
        return frozenset()
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    else:
        items = [value]
    hours: list[int] = []
    for item in items:
        try:
            hour = int(item)
        except (TypeError, ValueError):
            continue
        if 0 <= hour <= 23:
            hours.append(hour)
    return frozenset(hours)


def _directions_from_value(value: Any) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    else:
        items = [value]
    directions: list[str] = []
    for item in items:
        token = str(item).strip().lower()
        if token in {"long", "short"}:
            directions.append(token)
    return frozenset(directions)


def _hour_allowed_by_session(*, hour: int, session_range: object) -> bool:
    if not isinstance(session_range, str) or "-" not in session_range:
        return True
    left, right = session_range.split("-", 1)
    try:
        start = int(left.strip())
        end = int(right.strip())
    except ValueError:
        return True
    if not (0 <= start <= 23 and 0 <= end <= 23):
        return True
    if start <= end:
        return start <= hour <= end
    return hour >= start or hour <= end


def _blocked_hours_from_params(entry_params: Mapping[str, Any]) -> frozenset[int]:
    filters = entry_params.get("filters") if isinstance(entry_params.get("filters"), Mapping) else {}
    raw = entry_params.get("blocked_utc_hours", filters.get("blocked_utc_hours"))
    return _hours_from_value(raw)


def _blocked_local_direction_window_from_params(
    *,
    ts: Any,
    direction: str,
    entry_params: Mapping[str, Any],
) -> bool:
    filters = entry_params.get("filters") if isinstance(entry_params.get("filters"), Mapping) else {}
    raw_blocks = entry_params.get(
        "blocked_local_direction_windows",
        filters.get("blocked_local_direction_windows"),
    )
    if not isinstance(raw_blocks, (list, tuple)):
        return False
    current_ts = _as_datetime(ts)
    if current_ts is None:
        return False
    if current_ts.tzinfo is None:
        current_ts = current_ts.replace(tzinfo=timezone.utc)
    normalized_direction = str(direction).strip().lower()
    for block in raw_blocks:
        if not isinstance(block, Mapping):
            continue
        timezone_name = str(block.get("timezone", "UTC")).strip() or "UTC"
        try:
            local_ts = current_ts.astimezone(ZoneInfo(timezone_name))
        except Exception:
            continue
        weekdays = _weekdays_from_value(block.get("weekdays", block.get("weekday")))
        if weekdays and local_ts.weekday() not in weekdays:
            continue
        hours = _hours_from_value(block.get("hours", block.get("hour")))
        if hours and local_ts.hour not in hours:
            continue
        directions = _directions_from_value(block.get("directions", block.get("direction")))
        if directions and normalized_direction not in directions:
            continue
        return True
    return False


def _timeframe_to_minutes(timeframe: str) -> int:
    """Convert timeframe token (e.g., '5m', '1h') to minutes."""

    if timeframe.endswith("m"):
        return int(timeframe[:-1])
    if timeframe.endswith("h"):
        return int(timeframe[:-1]) * 60
    if timeframe.endswith("d"):
        return int(timeframe[:-1]) * 60 * 24
    raise ValueError(f"Unsupported timeframe '{timeframe}'")


def _register_plugin_for_strategy(
    *,
    engine: StrategyEngine,
    strategy_id: str,
    manifest_entry: Any,
) -> None:
    if strategy_id == "m1_baseline_ma_rsi":
        plugin = MovingAverageRsiStrategy()
        entry_params = (
            manifest_entry.parameters.get("entry", {})
            if hasattr(manifest_entry, "parameters")
            else {}
        )
        plugin.rsi_long_threshold = float(
            entry_params.get("rsi_long_threshold", plugin.rsi_long_threshold)
        )
        plugin.rsi_short_threshold = float(
            entry_params.get("rsi_short_threshold", plugin.rsi_short_threshold)
        )
        plugin.min_gap_pct = float(entry_params.get("min_gap_pct", plugin.min_gap_pct))
        plugin._cooldown_bars = int(entry_params.get("cooldown_bars", plugin.cooldown_bars()))
        engine.register_plugin(plugin)
        return
    if strategy_id == "m1_baseline_donchian":
        engine.register_plugin(DonchianBreakoutStrategy())
        return
    if strategy_id == "m1_baseline_donchian_long_only":
        engine.register_plugin(DonchianBreakoutLongOnlyStrategy())
        return
    if strategy_id == "m1_baseline_donchian_upper_only":
        engine.register_plugin(DonchianBreakoutUpperOnlyStrategy())
        return
    if strategy_id == "m1_us_session_trend_pullback":
        engine.register_plugin(UsSessionTrendPullbackStrategy())
        return
    raise KeyError(f"Unknown strategy '{strategy_id}' for PoC simulation")


@dataclass(slots=True)
class RiskState:
    """Tracks streak-aware risk sizing state."""

    current_risk_pct: float
    consecutive_wins: int = 0
    consecutive_losses: int = 0

    def update_after_trade(
        self, r_multiple: float, streak: StreakRules, base_risk_pct: float
    ) -> None:
        """Apply streak rules to adjust risk for the next trade."""

        if r_multiple > 0:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            if self.consecutive_wins >= streak.win_threshold:
                steps = self.consecutive_wins - streak.win_threshold + 1
                bumped = base_risk_pct + steps * streak.win_step_pct
                self.current_risk_pct = min(streak.win_cap_pct, bumped)
            else:
                self.current_risk_pct = base_risk_pct
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            if self.consecutive_losses >= streak.loss_threshold:
                self.current_risk_pct = streak.loss_risk_pct
            else:
                self.current_risk_pct = base_risk_pct
            if streak.reset_on_loss:
                self.consecutive_wins = 0


def simulate_paper_poc(
    *,
    strategy: str | None = "m1_baseline_ma_rsi",
    profile: str = "m1_baseline",
    window_from: str | None = None,
    window_to: str | None = None,
    spread_pips: float = 0.01,
    slippage_pips: float = 0.0,
    slippage_std: float = 0.0,
    commission_pct: float = 0.0,
    fixed_risk: bool = False,
    symbols: Sequence[str] | None = None,
    seed: int | None = None,
    entry_on_next_bar: bool = True,
    session_start_hour: int | None = None,
    session_end_hour: int | None = None,
    trail_atr_mult: float | None = None,
    risk_policy_path: Path = DEFAULT_RISK_POLICY,
    strategy_manifest_path: Path = DEFAULT_STRATEGY_MANIFEST,
    data_manifest_path: Path = DEFAULT_DATA_MANIFEST,
    feature_config_path: Path = DEFAULT_FEATURE_CONFIG,
    allocation_config_path: Path | None = None,
    allocation_profile: str | None = None,
    target_r_multiple: float = 2.0,
    ttl_bars: int = 12,
    export_returns: Path | None = DEFAULT_RETURNS_EXPORT,
    export_equity: Path | None = DEFAULT_EQUITY_EXPORT,
) -> PocResult:
    """Run a minimal paper-trading simulation and return aggregated metrics."""

    if (session_start_hour is None) ^ (session_end_hour is None):
        raise ValueError("session_start_hour and session_end_hour must be set together")
    if session_start_hour is not None:
        if not 0 <= session_start_hour <= 23 or not 0 <= session_end_hour <= 23:
            raise ValueError("session_start_hour/session_end_hour must be 0-23")
    if trail_atr_mult is not None and trail_atr_mult <= 0:
        raise ValueError("trail_atr_mult must be positive")

    effective_seed = seed if seed is not None else 0
    np.random.seed(effective_seed)

    strategy_manifest = StrategyManifest.load(strategy_manifest_path)
    if strategy is not None and strategy not in strategy_manifest.strategies:
        raise KeyError(f"Unknown strategy '{strategy}' for PoC simulation")
    _, selected_entries = _resolve_manifest_entries(strategy_manifest, strategy)
    selected_strategy_ids = [strategy_id for strategy_id, _ in selected_entries]
    if not selected_strategy_ids:
        raise ValueError("No strategies selected for PoC simulation")

    data_entries = {
        strategy_id: _load_data_manifest(data_manifest_path, strategy_id)
        for strategy_id in selected_strategy_ids
    }
    primary_strategy_id = selected_strategy_ids[0]
    primary_data_entry = data_entries[primary_strategy_id]

    watchlist_union: set[str] = set()
    for _, entry in selected_entries:
        if entry.watchlist:
            watchlist_union.update(symbol.upper() for symbol in entry.watchlist)
    resolved_symbols = symbols or sorted(watchlist_union) or ["USDJPY"]
    symbols = [s.strip().upper() for s in resolved_symbols if s.strip()]
    watchlist_datasets: dict[str, Mapping[str, Any]] = {}
    for data_entry in data_entries.values():
        for symbol, dataset in (data_entry.get("watchlist_datasets") or {}).items():
            symbol_key = str(symbol).upper()
            if symbol_key not in watchlist_datasets and isinstance(dataset, Mapping):
                watchlist_datasets[symbol_key] = dataset

    required_features: set[str] = set()
    for _strategy_id, entry in selected_entries:
        required_features.update(entry.metadata.required_feature_set)

    dataset_paths: list[str] = []
    dataset_hashes: list[str] = []

    pipeline = FeaturePipeline.from_config_file(feature_config_path)
    gate = _build_gate_state(symbols)
    risk_settings = _load_risk_policy(risk_policy_path, profile)
    default_limits = risk_settings.per_strategy_limits.get(
        primary_strategy_id,
        StrategyRiskLimits(per_trade_pct=risk_settings.base_per_trade_pct),
    )
    base_risk_pct = default_limits.per_trade_pct or risk_settings.base_per_trade_pct

    equity = risk_settings.base_equity
    all_trades: list[TradeRecord] = []
    dd_curve: list[float] = [equity]

    entry_params_by_strategy: dict[str, Mapping[str, Any]] = {}
    sizing_params_by_strategy: dict[str, Mapping[str, Any]] = {}
    for strategy_id, entry in selected_entries:
        params = entry.parameters if hasattr(entry, "parameters") else {}
        entry_params = params.get("entry", {}) if isinstance(params, Mapping) else {}
        sizing_params = params.get("sizing", {}) if isinstance(params, Mapping) else {}
        entry_params_by_strategy[strategy_id] = (
            entry_params if isinstance(entry_params, Mapping) else {}
        )
        sizing_params_by_strategy[strategy_id] = (
            sizing_params if isinstance(sizing_params, Mapping) else {}
        )

    primary_sizing_params = sizing_params_by_strategy.get(primary_strategy_id, {})
    tp_r_multiple = float(target_r_multiple)
    atr_sl_mult = float(primary_sizing_params.get("atr_sl_mult", 1.0))

    engine = StrategyEngine()
    for strategy_id, entry in selected_entries:
        _register_plugin_for_strategy(
            engine=engine,
            strategy_id=strategy_id,
            manifest_entry=entry,
        )
    engine._manifest = strategy_manifest  # type: ignore[attr-defined]
    if allocation_config_path is not None and allocation_config_path.exists():
        engine.set_allocation_policy(
            StrategyAllocationPolicy.load(
                allocation_config_path,
                profile=allocation_profile,
            )
        )

    # preload price+feature frames per symbol
    pf_by_symbol: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        ds_entry = watchlist_datasets.get(symbol) or {}
        ds_path = Path(ds_entry.get("path", primary_data_entry["dataset_path"]))
        ds_hash = ds_entry.get("sha256", primary_data_entry["dataset_sha256"])
        dataset_paths.append(str(ds_path))
        dataset_hashes.append(ds_hash)

        df = pd.read_parquet(ds_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        if window_from:
            df = df[df["timestamp"] >= pd.Timestamp(window_from)]
        if window_to:
            df = df[df["timestamp"] <= pd.Timestamp(window_to)]
        df = df.sort_values("timestamp").reset_index(drop=True)
        df = df.set_index("timestamp")
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
        if df.empty:
            continue
        feature_matrix = pipeline.compute_feature_matrix(symbol=symbol, price_df=df.reset_index())
        if feature_matrix.index.tz is None:
            feature_matrix.index = feature_matrix.index.tz_localize("UTC")
        else:
            feature_matrix.index = feature_matrix.index.tz_convert("UTC")
        pf_by_symbol[symbol] = df.join(feature_matrix, how="left")

    # build event stream
    events: list[tuple[pd.Timestamp, str, pd.Series]] = []
    for symbol, pf in pf_by_symbol.items():
        for ts, row in pf.iterrows():
            events.append((ts, symbol, row))
    events.sort(key=lambda x: x[0])

    risk_state = RiskState(current_risk_pct=base_risk_pct)
    open_positions: list[dict[str, Any]] = []
    pending_entries: list[dict[str, Any]] = []
    total_risk_soft = risk_settings.total_risk_soft_pct
    total_risk_hard = risk_settings.total_risk_hard_pct
    bucket_risk_cap = risk_settings.bucket_risk_cap_pct

    def _currencies(sym: str) -> tuple[str | None, str | None]:
        base = sym[:3].upper() if len(sym) >= 3 else None
        quote = sym[3:6].upper() if len(sym) >= 6 else None
        return base, quote

    # correlation matrix on closes (pct change)
    corr_matrix: dict[tuple[str, str], float] = {}
    if pf_by_symbol:
        returns = {}
        for sym, pf in pf_by_symbol.items():
            close = pf["close"].astype(float)
            returns[sym] = close.pct_change().dropna()
        symbols_for_corr = list(returns)
        for i, si in enumerate(symbols_for_corr):
            for sj in symbols_for_corr[i + 1 :]:
                if len(returns[si]) > 10 and len(returns[sj]) > 10:
                    corr = float(returns[si].corr(returns[sj]))
                    corr_matrix[(si, sj)] = corr
                    corr_matrix[(sj, si)] = corr

    engine_seed = effective_seed

    def _open_risk_pct_total(equity_value: float = equity) -> float:
        return sum((pos["risk_amount"] / equity_value) * 100 for pos in open_positions)

    def _open_risk_pct_bucket(sym: str, equity_value: float = equity) -> float:
        base, quote = _currencies(sym)
        pct = 0.0
        for pos in open_positions:
            b, q = _currencies(str(pos.get("symbol", "")))
            if (base and (b == base or q == base)) or (quote and (b == quote or q == quote)):
                pct += (pos["risk_amount"] / equity_value) * 100
        return pct

    def _bucket_overlap_count(sym: str) -> int:
        base, quote = _currencies(sym)

        def _overlaps(other_sym: str) -> bool:
            b, q = _currencies(other_sym)
            return (base and (b == base or q == base)) or (quote and (b == quote or q == quote))

        return sum(1 for pos in open_positions if _overlaps(str(pos.get("symbol", ""))))

    def _attempt_open_position(spec: Mapping[str, Any], *, current_ts: pd.Timestamp, current_row: pd.Series) -> None:
        spec_symbol = str(spec.get("symbol", symbol))
        strategy_for_signal = str(spec.get("strategy_id", primary_strategy_id))
        direction = str(spec.get("direction", "long"))
        entry_params_signal = entry_params_by_strategy.get(strategy_for_signal, {})
        sizing_params_signal = sizing_params_by_strategy.get(strategy_for_signal, {})
        atr_sl_mult_signal = float(sizing_params_signal.get("atr_sl_mult", atr_sl_mult))
        entry_tf_signal = str(entry_params_signal.get("timeframe", "5m"))
        ttl_minutes_signal = ttl_bars * _timeframe_to_minutes(entry_tf_signal)
        current_hour = current_ts.hour
        if not _hour_allowed_by_session(
            hour=current_hour,
            session_range=entry_params_signal.get("session_utc_range"),
        ):
            return
        if current_hour in _blocked_hours_from_params(entry_params_signal):
            return
        if _blocked_local_direction_window_from_params(
            ts=current_ts,
            direction=direction,
            entry_params=entry_params_signal,
        ):
            return

        entry_base_price = _safe_float(spec.get("entry_base_price"))
        if entry_base_price is None:
            open_value = _safe_float(current_row.get("open"))
            entry_base_price = open_value if open_value is not None else float(current_row["close"])
        atr_value = _safe_float(spec.get("atr_value"))
        if atr_value is None:
            atr_value = float(current_row.get("atr_14_1h", 0) or 0)
        trend_value = _safe_float(spec.get("trend_value"))
        if trend_value is None:
            trend_value = float(current_row.get("regime_trend_1h", 0) or 0)

        dyn_spread = _spread_for(spec_symbol, current_ts, spread_pips)
        slip = _slippage_for(spec_symbol, current_ts, slippage_pips, slippage_std)
        entry_price = (
            entry_base_price + dyn_spread + slip
            if direction == "long"
            else entry_base_price - dyn_spread - slip
        )
        level = spec.get("level")
        buffer = spec.get("buffer")
        if level is None:
            stop_buffer = atr_value * atr_sl_mult_signal
            if stop_buffer <= 0:
                return
            stop_price = entry_price - stop_buffer if direction == "long" else entry_price + stop_buffer
        else:
            if buffer is None or float(buffer) <= 0:
                buffer = max(0.08, atr_value * 0.03)
            stop_price = (float(level) - float(buffer)) if direction == "long" else (float(level) + float(buffer))

        risk_distance = abs(entry_price - stop_price)
        if risk_distance <= 0:
            return

        signal_limits = risk_settings.per_strategy_limits.get(
            strategy_for_signal,
            StrategyRiskLimits(per_trade_pct=risk_settings.base_per_trade_pct),
        )
        base_risk_for_strategy = signal_limits.per_trade_pct or risk_settings.base_per_trade_pct
        new_risk_pct = min(risk_state.current_risk_pct, base_risk_for_strategy)
        overall_limit = signal_limits.max_concurrent_overall
        bucket_limit = signal_limits.max_concurrent_bucket
        r_eff_soft = signal_limits.r_eff_soft or risk_settings.r_eff_soft
        r_eff_hard = signal_limits.r_eff_hard or risk_settings.r_eff_hard

        total_after = _open_risk_pct_total() + new_risk_pct
        if total_risk_hard and total_after > total_risk_hard:
            return
        if total_risk_soft and total_after > total_risk_soft:
            return
        if bucket_risk_cap:
            bucket_after = _open_risk_pct_bucket(spec_symbol) + new_risk_pct
            if bucket_after > bucket_risk_cap:
                return
        if risk_settings.corr_group_risk_cap_pct and corr_matrix:
            group_pct = new_risk_pct
            for pos in open_positions:
                pos_symbol = str(pos.get("symbol", ""))
                corr = corr_matrix.get((spec_symbol, pos_symbol), 0.0)
                if corr >= 0.7:
                    group_pct += (pos["risk_amount"] / equity) * 100
            if group_pct > risk_settings.corr_group_risk_cap_pct:
                return
        if r_eff_hard and total_after > r_eff_hard:
            return
        if r_eff_soft and total_after > r_eff_soft:
            return
        if overall_limit is not None and len(open_positions) >= overall_limit:
            return
        if bucket_limit is not None and _bucket_overlap_count(spec_symbol) >= bucket_limit:
            return

        equity_for_risk = risk_settings.base_equity if fixed_risk else equity
        risk_amount = equity_for_risk * (new_risk_pct / 100)
        target_price = (
            entry_price + tp_r_multiple * risk_distance
            if direction == "long"
            else entry_price - tp_r_multiple * risk_distance
        )
        open_positions.append(
            {
                "strategy_id": strategy_for_signal,
                "symbol": spec_symbol,
                "base_risk_pct": base_risk_for_strategy,
                "direction": direction,
                "entry": entry_price,
                "stop": stop_price,
                "target": target_price,
                "risk_distance": risk_distance,
                "risk_amount": risk_amount,
                "opened_at": current_ts,
                "expire_at": current_ts.to_pydatetime() + pd.Timedelta(minutes=ttl_minutes_signal),
                "breakout": spec.get("breakout"),
                "level": level,
                "buffer": buffer,
                "breakout_width": spec.get("breakout_width"),
                "quality_score": spec.get("quality_score"),
                "filter_flags": spec.get("filter_flags"),
                "trend_value": trend_value,
                "atr_value": atr_value,
                "spread_used": dyn_spread,
                "slippage_used": slip,
            }
        )

    for ts, symbol, row in events:
        for strategy_id, entry in selected_entries:
            entry.watchlist = [symbol]
            strategy_manifest.strategies[strategy_id] = entry

        symbol_positions = [pos for pos in open_positions if pos["symbol"] == symbol]
        if symbol_positions:
            low = float(row["low"])
            high = float(row["high"])
            close = float(row["close"])
            atr_value = float(row.get("atr_14_1h", 0) or 0)
            dyn_spread = _spread_for(symbol, ts, spread_pips)
            for pos in list(symbol_positions):
                direction = pos["direction"]
                exit_price: float | None = None
                if trail_atr_mult is not None and atr_value > 0:
                    trail_distance = max(0.05, atr_value * trail_atr_mult)
                    if direction == "long":
                        pos["stop"] = max(pos["stop"], high - trail_distance)
                    else:
                        pos["stop"] = min(pos["stop"], low + trail_distance)
                if direction == "long":
                    if low <= pos["stop"]:
                        slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
                        exit_price = _exit_with_cost(
                            price=pos["stop"],
                            direction=direction,
                            spread=dyn_spread,
                            slippage=slip,
                        )
                    elif high >= pos["target"]:
                        slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
                        exit_price = _exit_with_cost(
                            price=pos["target"],
                            direction=direction,
                            spread=dyn_spread,
                            slippage=slip,
                        )
                else:
                    if high >= pos["stop"]:
                        slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
                        exit_price = _exit_with_cost(
                            price=pos["stop"],
                            direction=direction,
                            spread=dyn_spread,
                            slippage=slip,
                        )
                    elif low <= pos["target"]:
                        slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
                        exit_price = _exit_with_cost(
                            price=pos["target"],
                            direction=direction,
                            spread=dyn_spread,
                            slippage=slip,
                        )

                if exit_price is None and ts.to_pydatetime() >= pos["expire_at"]:
                    slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
                    exit_price = _exit_with_cost(
                        price=close,
                        direction=direction,
                        spread=dyn_spread,
                        slippage=slip,
                    )

                if exit_price is not None:
                    risk_distance = pos["risk_distance"]
                    if direction == "long":
                        r_multiple = (exit_price - pos["entry"]) / risk_distance
                        pnl = r_multiple * pos["risk_amount"]
                    else:
                        r_multiple = (pos["entry"] - exit_price) / risk_distance
                        pnl = r_multiple * pos["risk_amount"]
                    if commission_pct:
                        pnl -= pos["risk_amount"] * (commission_pct / 100.0)
                    equity += pnl
                    risk_state.update_after_trade(
                        r_multiple,
                        risk_settings.streak,
                        float(pos.get("base_risk_pct", base_risk_pct)),
                    )
                    all_trades.append(
                        TradeRecord(
                            strategy_id=pos.get("strategy_id"),
                            opened_at=pos["opened_at"].to_pydatetime(),
                            closed_at=ts.to_pydatetime(),
                            symbol=symbol,
                            direction=direction,
                            entry=pos["entry"],
                            exit=exit_price,
                            stop=pos["stop"],
                            target=pos["target"],
                            r_multiple=round(float(r_multiple), 4),
                            pnl=round(float(pnl), 2),
                            breakout=pos.get("breakout"),
                            level=pos.get("level"),
                            buffer=pos.get("buffer"),
                            breakout_width=pos.get("breakout_width"),
                            quality_score=pos.get("quality_score"),
                            filter_flags=pos.get("filter_flags"),
                            trend_value=pos.get("trend_value"),
                            atr_value=pos.get("atr_value"),
                            spread_used=pos.get("spread_used"),
                            slippage_used=pos.get("slippage_used"),
                        )
                    )
                    open_positions.remove(pos)

        if session_start_hour is not None:
            hour = ts.hour
            if session_start_hour <= session_end_hour:
                if not (session_start_hour <= hour <= session_end_hour):
                    dd_curve.append(equity)
                    continue
            else:
                if not (hour >= session_start_hour or hour <= session_end_hour):
                    dd_curve.append(equity)
                    continue

        pending_for_symbol = [item for item in pending_entries if str(item.get("symbol")) == symbol]
        if pending_for_symbol:
            for pending in pending_for_symbol:
                _attempt_open_position(pending, current_ts=ts, current_row=row)
                pending_entries.remove(pending)

        feature_context, clock = _feature_context_for_row(pipeline, [symbol], row)
        if not feature_context.feature_frame(symbol):
            dd_curve.append(equity)
            continue
        if any(pd.isna(row.get(key)) for key in required_features):
            dd_curve.append(equity)
            continue

        account = SimpleNamespace(equity=equity)
        config_snapshot = SimpleNamespace(cfg_hash="poc")
        regime = SimpleNamespace(mode="normal")
        signals = engine.run_all(
            features=feature_context,
            regime=regime,
            gate=gate,
            account=account,
            config=config_snapshot,
            clock=clock,
            watchlist=[symbol],
            seed=engine_seed,
        )
        if not signals:
            dd_curve.append(equity)
            continue

        for signal in signals:
            spec = {
                "symbol": symbol,
                "strategy_id": str(getattr(signal, "strategy_id", primary_strategy_id)),
                "direction": str(getattr(signal, "direction", "long")),
                "level": getattr(signal, "level", None),
                "buffer": getattr(signal, "buffer", None),
                "breakout": getattr(signal, "breakout", None),
                "breakout_width": getattr(signal, "breakout_width", None),
                "quality_score": getattr(signal, "quality_score", None),
                "filter_flags": getattr(signal, "filter_flags", None),
                "trend_value": float(row.get("regime_trend_1h", 0) or 0),
                "atr_value": float(row.get("atr_14_1h", 0) or 0),
            }
            if entry_on_next_bar:
                pending_entries.append(spec)
            else:
                spec["entry_base_price"] = float(row["close"])
                _attempt_open_position(spec, current_ts=ts, current_row=row)
        dd_curve.append(equity)

    # close any residual open positions at final price
    if events and open_positions:
        last_ts = events[-1][0]
        for pos in list(open_positions):
            symbol = str(pos["symbol"])
            row = pf_by_symbol[symbol].iloc[-1]
            close = float(row["close"])
            dyn_spread = _spread_for(symbol, last_ts, spread_pips)
            slip = _slippage_for(symbol, last_ts, slippage_pips, slippage_std)
            exit_price = _exit_with_cost(
                price=close,
                direction=pos["direction"],
                spread=dyn_spread,
                slippage=slip,
            )
            risk_distance = pos["risk_distance"]
            if pos["direction"] == "long":
                r_multiple = (exit_price - pos["entry"]) / risk_distance
                pnl = r_multiple * pos["risk_amount"]
            else:
                r_multiple = (pos["entry"] - exit_price) / risk_distance
                pnl = r_multiple * pos["risk_amount"]
            if commission_pct:
                pnl -= pos["risk_amount"] * (commission_pct / 100.0)
            equity += pnl
            risk_state.update_after_trade(
                r_multiple,
                risk_settings.streak,
                float(pos.get("base_risk_pct", base_risk_pct)),
            )
            all_trades.append(
                TradeRecord(
                    strategy_id=pos.get("strategy_id"),
                    opened_at=pos["opened_at"].to_pydatetime(),
                    closed_at=last_ts.to_pydatetime(),
                    symbol=symbol,
                    direction=pos["direction"],
                    entry=pos["entry"],
                    exit=exit_price,
                    stop=pos["stop"],
                    target=pos["target"],
                    r_multiple=round(float(r_multiple), 4),
                    pnl=round(float(pnl), 2),
                    breakout=pos.get("breakout"),
                    level=pos.get("level"),
                    buffer=pos.get("buffer"),
                    breakout_width=pos.get("breakout_width"),
                    quality_score=pos.get("quality_score"),
                    filter_flags=pos.get("filter_flags"),
                    trend_value=pos.get("trend_value"),
                    atr_value=pos.get("atr_value"),
                    spread_used=pos.get("spread_used"),
                    slippage_used=pos.get("slippage_used"),
                )
            )
            open_positions.remove(pos)
        dd_curve.append(equity)

    wins = [t for t in all_trades if t.r_multiple > 0]
    losses = [t for t in all_trades if t.r_multiple <= 0]
    pf_all = (
        (sum(t.pnl for t in wins) / abs(sum(t.pnl for t in losses)) if losses else 1.0)
        if all_trades
        else 1.0
    )
    win_rate = len(wins) / len(all_trades) if all_trades else 0.0
    avg_r = sum(t.r_multiple for t in all_trades) / len(all_trades) if all_trades else 0.0
    equity_series = pd.Series(dd_curve)
    running_max = equity_series.cummax()
    drawdowns = (equity_series - running_max) / running_max.replace(0, pd.NA)
    max_drawdown = abs(drawdowns.min()) if not drawdowns.empty else 0.0
    end_equity = equity

    metrics = {
        "pf_all": round(float(pf_all), 4),
        "win_rate": round(float(win_rate), 4),
        "avg_r": round(float(avg_r), 4),
        "max_drawdown": round(float(max_drawdown), 4),
        "trades": len(all_trades),
        "start_equity": round(float(risk_settings.base_equity), 2),
        "end_equity": round(float(end_equity), 2),
    }
    returns_series = equity_series.pct_change().dropna()
    window = {"from": window_from, "to": window_to}
    result = PocResult(
        metrics=metrics,
        trades=all_trades,
        dataset_path=dataset_paths if len(dataset_paths) > 1 else dataset_paths[0],
        dataset_hash=dataset_hashes if len(dataset_hashes) > 1 else dataset_hashes[0],
        window=window,
        seed_used=effective_seed,
        returns=list(returns_series),
        equity_curve=list(equity_series),
    )
    _export_series(export_returns, "r", returns_series)
    _export_series(export_equity, "equity", equity_series)
    return result


def _export_series(path: Path | None, name: str, series: pd.Series) -> None:
    if not path:
        return
    target = path if path.suffix else path.with_suffix(".parquet")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        series.to_frame(name=name).to_parquet(target)
    except Exception:
        csv_path = target.with_suffix(".csv")
        series.to_frame(name=name).to_csv(csv_path, index=False)
