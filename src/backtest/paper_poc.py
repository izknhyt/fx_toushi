"""Lightweight paper-trading PoC simulator.

This module stitches together the feature pipeline, strategy engine, and a
deterministic trade loop so we can run a one-month style paper simulation
without broker connectivity.  It mirrors the PoC scope outlined in
`detailed_design_fx_signal_tool_v1.md` §0.6.14 and emits metrics compatible
with the PoC templates under `reports/backtest/`.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping
import numpy as np

import json
import math
import pandas as pd
import yaml

from src.features.pipeline import FeaturePipeline
from src.strategies.ma_rsi import MovingAverageRsiStrategy
from src.strategies.donchian import DonchianBreakoutStrategy
from src.strategies.registry import StrategyEngine, StrategyManifest

DEFAULT_DATA_MANIFEST = Path("reports") / "data_manifest.json"
DEFAULT_STRATEGY_MANIFEST = Path("config") / "strategy_manifest.yaml"
DEFAULT_FEATURE_CONFIG = Path("config") / "feature_pipeline.yaml"
DEFAULT_RISK_POLICY = Path("config") / "risk_policy.yaml"


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

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "metrics": dict(self.metrics),
            "trades": [trade.as_dict() for trade in self.trades],
            "dataset_path": self.dataset_path,
            "dataset_hash": self.dataset_hash,
            "window": self.window,
        }


def _load_data_manifest(path: Path, strategy: str) -> Mapping[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entry = manifest.get("strategies", {}).get(strategy)
    if not entry:
        raise KeyError(f"Strategy '{strategy}' missing in {path}")
    if "dataset_path" not in entry or "dataset_sha256" not in entry:
        raise ValueError(f"Strategy '{strategy}' manifest entry missing dataset information")
    return entry


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
            r_eff_soft=float(raw.get("exposure_r_eff_soft_stop", limits.get("exposure_r_eff_soft_stop", 2.0))),
            r_eff_hard=float(raw.get("exposure_r_eff_hard_stop", limits.get("exposure_r_eff_hard_stop", 2.5))),
            max_concurrent_overall=int(raw.get("max_concurrent_positions", {}).get("overall", 1))
            if isinstance(raw.get("max_concurrent_positions"), dict)
            else None,
            max_concurrent_bucket=int(raw.get("max_concurrent_positions", {}).get("per_currency_bucket", 1))
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


def _timeframe_to_minutes(timeframe: str) -> int:
    """Convert timeframe token (e.g., '5m', '1h') to minutes."""

    if timeframe.endswith("m"):
        return int(timeframe[:-1])
    if timeframe.endswith("h"):
        return int(timeframe[:-1]) * 60
    if timeframe.endswith("d"):
        return int(timeframe[:-1]) * 60 * 24
    raise ValueError(f"Unsupported timeframe '{timeframe}'")


@dataclass(slots=True)
class RiskState:
    """Tracks streak-aware risk sizing state."""

    current_risk_pct: float
    consecutive_wins: int = 0
    consecutive_losses: int = 0

    def update_after_trade(self, r_multiple: float, streak: StreakRules, base_risk_pct: float) -> None:
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
    strategy: str = "m1_baseline_ma_rsi",
    profile: str = "m1_baseline",
    window_from: str | None = None,
    window_to: str | None = None,
    spread_pips: float = 0.01,
    slippage_pips: float = 0.0,
    slippage_std: float = 0.0,
    commission_pct: float = 0.0,
    fixed_risk: bool = False,
    risk_policy_path: Path = DEFAULT_RISK_POLICY,
    strategy_manifest_path: Path = DEFAULT_STRATEGY_MANIFEST,
    data_manifest_path: Path = DEFAULT_DATA_MANIFEST,
    feature_config_path: Path = DEFAULT_FEATURE_CONFIG,
    target_r_multiple: float = 2.0,
    ttl_bars: int = 12,
) -> PocResult:
    """Run a minimal paper-trading simulation and return aggregated metrics."""

    data_entry = _load_data_manifest(data_manifest_path, strategy)
    strategy_manifest = StrategyManifest.load(strategy_manifest_path)
    manifest_entry = strategy_manifest.strategies[strategy]
    # narrow manifest to the single strategy to avoid registry mismatch
    strategy_manifest.strategies = {strategy: manifest_entry}
    watchlist = manifest_entry.watchlist
    required_features = manifest_entry.metadata.required_feature_set
    symbols = list(watchlist or ("USDJPY",))
    watchlist_datasets = data_entry.get("watchlist_datasets", {})

    dataset_paths: list[str] = []
    dataset_hashes: list[str] = []

    pipeline = FeaturePipeline.from_config_file(feature_config_path)
    gate = _build_gate_state(symbols)
    risk_settings = _load_risk_policy(risk_policy_path, profile)
    per_strategy_limits = risk_settings.per_strategy_limits.get(
        strategy, StrategyRiskLimits(per_trade_pct=risk_settings.base_per_trade_pct)
    )
    base_risk_pct = per_strategy_limits.per_trade_pct or risk_settings.base_per_trade_pct

    equity = risk_settings.base_equity
    all_trades: list[TradeRecord] = []
    dd_curve: list[float] = [equity]

    entry_params = manifest_entry.parameters.get("entry", {}) if hasattr(manifest_entry, "parameters") else {}
    sizing_params = manifest_entry.parameters.get("sizing", {}) if hasattr(manifest_entry, "parameters") else {}
    entry_tf = str(entry_params.get("timeframe", "5m"))
    ttl_minutes = ttl_bars * _timeframe_to_minutes(entry_tf)
    tp_r_multiple = float(sizing_params.get("tp_r_multiple", target_r_multiple))
    atr_sl_mult = float(sizing_params.get("atr_sl_mult", 1.0))

    engine = StrategyEngine()
    if strategy == "m1_baseline_ma_rsi":
        ma_plugin = MovingAverageRsiStrategy()
        entry_params = manifest_entry.parameters.get("entry", {}) if hasattr(manifest_entry, "parameters") else {}
        sizing_params = manifest_entry.parameters.get("sizing", {}) if hasattr(manifest_entry, "parameters") else {}
        ma_plugin.rsi_long_threshold = float(entry_params.get("rsi_long_threshold", ma_plugin.rsi_long_threshold))
        ma_plugin.rsi_short_threshold = float(entry_params.get("rsi_short_threshold", ma_plugin.rsi_short_threshold))
        ma_plugin.min_gap_pct = float(entry_params.get("min_gap_pct", ma_plugin.min_gap_pct))
        ma_plugin._cooldown_bars = int(entry_params.get("cooldown_bars", ma_plugin.cooldown_bars()))
        # TP/SL/TTL handled in sizing_params below
        engine.register_plugin(ma_plugin)
    elif strategy == "m1_baseline_donchian":
        engine.register_plugin(DonchianBreakoutStrategy())
    else:
        raise KeyError(f"Unknown strategy '{strategy}' for PoC simulation")
    engine._manifest = strategy_manifest  # type: ignore[attr-defined]

    # preload price+feature frames per symbol
    pf_by_symbol: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        ds_entry = watchlist_datasets.get(symbol) or {}
        ds_path = Path(ds_entry.get("path", data_entry["dataset_path"]))
        ds_hash = ds_entry.get("sha256", data_entry["dataset_sha256"])
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
        if df.empty:
            continue
        feature_matrix = pipeline.compute_feature_matrix(symbol=symbol, price_df=df.reset_index())
        pf_by_symbol[symbol] = df.join(feature_matrix, how="left")

    # build event stream
    events: list[tuple[pd.Timestamp, str, pd.Series]] = []
    for symbol, pf in pf_by_symbol.items():
        for ts, row in pf.iterrows():
            events.append((ts, symbol, row))
    events.sort(key=lambda x: x[0])

    risk_state = RiskState(current_risk_pct=base_risk_pct)
    open_positions: dict[str, dict[str, Any]] = {}
    overall_limit = per_strategy_limits.max_concurrent_overall
    bucket_limit = per_strategy_limits.max_concurrent_bucket
    total_risk_soft = risk_settings.total_risk_soft_pct
    total_risk_hard = risk_settings.total_risk_hard_pct
    bucket_risk_cap = risk_settings.bucket_risk_cap_pct
    r_eff_soft = risk_settings.r_eff_soft or per_strategy_limits.r_eff_soft
    r_eff_hard = risk_settings.r_eff_hard or per_strategy_limits.r_eff_hard

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

    for ts, symbol, row in events:
        manifest_entry.watchlist = [symbol]
        strategy_manifest.strategies[strategy] = manifest_entry

        if symbol in open_positions:
            pos = open_positions[symbol]
            low = float(row["low"])
            high = float(row["high"])
            close = float(row["close"])
            direction = pos["direction"]
            exit_price: float | None = None

            dyn_spread = _spread_for(symbol, ts, spread_pips)
            if direction == "long":
                if low <= pos["stop"]:
                    slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
                    exit_price = pos["stop"] - slip
                elif high >= pos["target"]:
                    slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
                    exit_price = pos["target"] - slip
            else:
                if high >= pos["stop"]:
                    slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
                    exit_price = pos["stop"] + slip
                elif low <= pos["target"]:
                    slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
                    exit_price = pos["target"] + slip

            if exit_price is None and ts.to_pydatetime() >= pos["expire_at"]:
                padding = dyn_spread if direction == "long" else -dyn_spread
                slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
                exit_price = close - padding - (slip if direction == "long" else -slip)

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
                risk_state.update_after_trade(r_multiple, risk_settings.streak, base_risk_pct)
                all_trades.append(
                    TradeRecord(
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
                    )
                )
                open_positions.pop(symbol, None)
            dd_curve.append(equity)
            continue

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
            seed=manifest_entry.priority,
        )
        if not signals:
            dd_curve.append(equity)
            continue

        signal = signals[0]
        direction = getattr(signal, "direction", "long")
        close_price = float(row["close"])
        atr_value = float(row.get("atr_14_1h", 0) or 0)

        dyn_spread = _spread_for(symbol, ts, spread_pips)
        if strategy == "m1_baseline_ma_rsi":
            stop_buffer = atr_value * atr_sl_mult
            if stop_buffer <= 0:
                dd_curve.append(equity)
                continue
            slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
            entry_price = close_price + dyn_spread + slip if direction == "long" else close_price - dyn_spread - slip
            stop_price = entry_price - stop_buffer if direction == "long" else entry_price + stop_buffer
        else:
            buffer = getattr(signal, "buffer", None)
            if buffer is None or buffer <= 0:
                buffer = max(0.08, atr_value * 0.03)
            level = getattr(signal, "level", close_price)
            slip = _slippage_for(symbol, ts, slippage_pips, slippage_std)
            entry_price = close_price + dyn_spread + slip if direction == "long" else close_price - dyn_spread - slip
            stop_price = (level - buffer) if direction == "long" else (level + buffer)

        risk_distance = abs(entry_price - stop_price)
        if risk_distance <= 0:
            dd_curve.append(equity)
            continue

        # open risk constraints
        def _open_risk_pct_total() -> float:
            return sum((pos["risk_amount"] / equity) * 100 for pos in open_positions.values())

        def _open_risk_pct_bucket(sym: str) -> float:
            base, quote = _currencies(sym)
            pct = 0.0
            for s, pos in open_positions.items():
                b, q = _currencies(s)
                if (base and (b == base or q == base)) or (quote and (b == quote or q == quote)):
                    pct += (pos["risk_amount"] / equity) * 100
            return pct

        new_risk_pct = risk_state.current_risk_pct
        total_after = _open_risk_pct_total() + new_risk_pct
        if total_risk_hard and total_after > total_risk_hard:
            dd_curve.append(equity)
            continue
        if total_risk_soft and total_after > total_risk_soft:
            dd_curve.append(equity)
            continue
        if bucket_risk_cap:
            bucket_after = _open_risk_pct_bucket(symbol) + new_risk_pct
            if bucket_after > bucket_risk_cap:
                dd_curve.append(equity)
                continue
        if risk_settings.corr_group_risk_cap_pct and corr_matrix:
            group_pct = new_risk_pct
            for s, pos in open_positions.items():
                corr = corr_matrix.get((symbol, s), 0.0)
                if corr >= 0.7:
                    group_pct += (pos["risk_amount"] / equity) * 100
            if group_pct > risk_settings.corr_group_risk_cap_pct:
                dd_curve.append(equity)
                continue
        if r_eff_hard and total_after > r_eff_hard:
            dd_curve.append(equity)
            continue
        if r_eff_soft and total_after > r_eff_soft:
            dd_curve.append(equity)
            continue

        if overall_limit is not None and len(open_positions) >= overall_limit:
            dd_curve.append(equity)
            continue
        if bucket_limit is not None:
            base, quote = _currencies(symbol)
            def _overlaps(sym: str) -> bool:
                b, q = _currencies(sym)
                return (base and (b == base or q == base)) or (quote and (b == quote or q == quote))
            open_count_same_bucket = sum(1 for sym in open_positions if _overlaps(sym))
            if open_count_same_bucket >= bucket_limit:
                dd_curve.append(equity)
                continue

        equity_for_risk = risk_settings.base_equity if fixed_risk else equity
        risk_amount = equity_for_risk * (risk_state.current_risk_pct / 100)
        target_price = (
            entry_price + tp_r_multiple * risk_distance
            if direction == "long"
            else entry_price - tp_r_multiple * risk_distance
        )
        open_positions[symbol] = {
            "direction": direction,
            "entry": entry_price,
            "stop": stop_price,
            "target": target_price,
            "risk_distance": risk_distance,
            "risk_amount": risk_amount,
            "opened_at": ts,
            "expire_at": ts.to_pydatetime() + pd.Timedelta(minutes=ttl_minutes),
        }
        dd_curve.append(equity)

    # close any residual open positions at final price
    if events and open_positions:
        last_ts = events[-1][0]
        for symbol, pos in list(open_positions.items()):
            row = pf_by_symbol[symbol].iloc[-1]
            close = float(row["close"])
            dyn_spread = _spread_for(symbol, last_ts, spread_pips)
            slip = _slippage_for(symbol, last_ts, slippage_pips, slippage_std)
            exit_price = close - dyn_spread - slip if pos["direction"] == "long" else close + dyn_spread + slip
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
            risk_state.update_after_trade(r_multiple, risk_settings.streak, base_risk_pct)
            all_trades.append(
                TradeRecord(
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
                )
            )
            open_positions.pop(symbol, None)
        dd_curve.append(equity)

    wins = [t for t in all_trades if t.r_multiple > 0]
    losses = [t for t in all_trades if t.r_multiple <= 0]
    pf_all = (sum(t.pnl for t in wins) / abs(sum(t.pnl for t in losses)) if losses else 1.0) if all_trades else 1.0
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
    window = {"from": window_from, "to": window_to}
    return PocResult(
        metrics=metrics,
        trades=all_trades,
        dataset_path=dataset_paths if len(dataset_paths) > 1 else dataset_paths[0],
        dataset_hash=dataset_hashes if len(dataset_hashes) > 1 else dataset_hashes[0],
        window=window,
    )
