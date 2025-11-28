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

import json
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


@dataclass(slots=True)
class TradeRecord:
    """Captured trade lifecycle for the PoC simulator."""

    opened_at: datetime
    closed_at: datetime
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
    dataset_path: str
    dataset_hash: str
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
    risk_policy_path: Path = DEFAULT_RISK_POLICY,
    strategy_manifest_path: Path = DEFAULT_STRATEGY_MANIFEST,
    data_manifest_path: Path = DEFAULT_DATA_MANIFEST,
    feature_config_path: Path = DEFAULT_FEATURE_CONFIG,
    target_r_multiple: float = 2.0,
    ttl_bars: int = 12,
) -> PocResult:
    """Run a minimal paper-trading simulation and return aggregated metrics."""

    data_entry = _load_data_manifest(data_manifest_path, strategy)
    dataset_path = Path(data_entry["dataset_path"])
    dataset_hash = data_entry["dataset_sha256"]

    strategy_manifest = StrategyManifest.load(strategy_manifest_path)
    manifest_entry = strategy_manifest.strategies[strategy]
    # narrow manifest to the single strategy to avoid registry mismatch
    strategy_manifest.strategies = {strategy: manifest_entry}
    watchlist = manifest_entry.watchlist
    required_features = manifest_entry.metadata.required_feature_set
    symbol = next(iter(watchlist or ("USDJPY",)))

    df = pd.read_parquet(dataset_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if window_from:
        df = df[df["timestamp"] >= pd.Timestamp(window_from)]
    if window_to:
        df = df[df["timestamp"] <= pd.Timestamp(window_to)]
    df = df.sort_values("timestamp").reset_index(drop=True)
    if df.empty:
        empty_metrics = {
            "pf_all": 1.0,
            "win_rate": 0.0,
            "avg_r": 0.0,
            "max_drawdown": 0.0,
            "trades": 0,
            "start_equity": 0.0,
            "end_equity": 0.0,
        }
        window = {"from": window_from, "to": window_to}
        return PocResult(
            metrics=empty_metrics,
            trades=[],
            dataset_path=str(dataset_path),
            dataset_hash=dataset_hash,
            window=window,
        )
    df = df.set_index("timestamp")

    pipeline = FeaturePipeline.from_config_file(feature_config_path)
    feature_matrix = pipeline.compute_feature_matrix(symbol=symbol, price_df=df.reset_index())
    price_and_features = df.join(feature_matrix, how="left")

    engine = StrategyEngine()
    if strategy == "m1_baseline_ma_rsi":
        engine.register_plugin(MovingAverageRsiStrategy())
    elif strategy == "m1_baseline_donchian":
        engine.register_plugin(DonchianBreakoutStrategy())
    else:
        raise KeyError(f"Unknown strategy '{strategy}' for PoC simulation")
    engine._manifest = strategy_manifest  # type: ignore[attr-defined]

    gate = _build_gate_state(watchlist)
    risk_settings = _load_risk_policy(risk_policy_path, profile)
    per_strategy_limits = risk_settings.per_strategy_limits.get(
        strategy, StrategyRiskLimits(per_trade_pct=risk_settings.base_per_trade_pct)
    )
    base_risk_pct = per_strategy_limits.per_trade_pct or risk_settings.base_per_trade_pct
    risk_state = RiskState(current_risk_pct=base_risk_pct)
    equity = risk_settings.base_equity
    trades: list[TradeRecord] = []
    equity_curve: list[float] = [equity]
    open_position: dict[str, Any] | None = None
    entry_params = manifest_entry.parameters.get("entry", {}) if hasattr(manifest_entry, "parameters") else {}
    sizing_params = manifest_entry.parameters.get("sizing", {}) if hasattr(manifest_entry, "parameters") else {}
    entry_tf = str(entry_params.get("timeframe", "5m"))
    ttl_minutes = ttl_bars * _timeframe_to_minutes(entry_tf)
    tp_r_multiple = float(sizing_params.get("tp_r_multiple", target_r_multiple))
    atr_sl_mult = float(sizing_params.get("atr_sl_mult", 1.0))

    for ts, row in price_and_features.iterrows():
        if open_position:
            low = float(row["low"])
            high = float(row["high"])
            close = float(row["close"])
            direction = open_position["direction"]
            exit_price: float | None = None
            exit_reason: str | None = None

            if direction == "long":
                if low <= open_position["stop"]:
                    exit_price, exit_reason = open_position["stop"], "stop"
                elif high >= open_position["target"]:
                    exit_price, exit_reason = open_position["target"], "target"
            else:
                if high >= open_position["stop"]:
                    exit_price, exit_reason = open_position["stop"], "stop"
                elif low <= open_position["target"]:
                    exit_price, exit_reason = open_position["target"], "target"

            if exit_price is None and ts.to_pydatetime() >= open_position["expire_at"]:
                padding = spread_pips if direction == "long" else -spread_pips
                exit_price = close - padding
                exit_reason = "ttl"

            if exit_price is not None:
                risk_distance = open_position["risk_distance"]
                if direction == "long":
                    r_multiple = (exit_price - open_position["entry"]) / risk_distance
                    pnl = r_multiple * open_position["risk_amount"]
                else:
                    r_multiple = (open_position["entry"] - exit_price) / risk_distance
                    pnl = r_multiple * open_position["risk_amount"]
                equity += pnl
                risk_state.update_after_trade(r_multiple, risk_settings.streak, base_risk_pct)
                trades.append(
                    TradeRecord(
                        opened_at=open_position["opened_at"].to_pydatetime(),
                        closed_at=ts.to_pydatetime(),
                        direction=direction,
                        entry=open_position["entry"],
                        exit=exit_price,
                        stop=open_position["stop"],
                        target=open_position["target"],
                        r_multiple=round(float(r_multiple), 4),
                        pnl=round(float(pnl), 2),
                    )
                )
                open_position = None
            equity_curve.append(equity)
            continue

        feature_context, clock = _feature_context_for_row(pipeline, watchlist, row)
        if not feature_context.feature_frame(symbol):
            continue
        if any(pd.isna(row.get(key)) for key in required_features):
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
            watchlist=watchlist,
            seed=manifest_entry.priority,
        )
        if not signals:
            equity_curve.append(equity)
            continue

        signal = signals[0]
        direction = getattr(signal, "direction", "long")
        close_price = float(row["close"])
        atr_value = float(row.get("atr_14_1h", 0) or 0)

        # Strategy-specific sizing
        if strategy == "m1_baseline_ma_rsi":
            stop_buffer = atr_value * atr_sl_mult
            if stop_buffer <= 0:
                equity_curve.append(equity)
                continue
            entry_price = close_price + spread_pips if direction == "long" else close_price - spread_pips
            stop_price = entry_price - stop_buffer if direction == "long" else entry_price + stop_buffer
        else:  # donchian breakout
            buffer = getattr(signal, "buffer", None)
            if buffer is None or buffer <= 0:
                buffer = max(0.05, atr_value * 0.02)
            level = getattr(signal, "level", close_price)
            entry_price = close_price + spread_pips if direction == "long" else close_price - spread_pips
            stop_price = (level - buffer) if direction == "long" else (level + buffer)

        risk_distance = abs(entry_price - stop_price)
        if risk_distance <= 0:
            equity_curve.append(equity)
            continue

        risk_amount = equity * (risk_state.current_risk_pct / 100)
        target_price = (
            entry_price + tp_r_multiple * risk_distance
            if direction == "long"
            else entry_price - tp_r_multiple * risk_distance
        )
        open_position = {
            "direction": direction,
            "entry": entry_price,
            "stop": stop_price,
            "target": target_price,
            "risk_distance": risk_distance,
            "risk_amount": risk_amount,
            "opened_at": ts,
            "expire_at": ts.to_pydatetime() + pd.Timedelta(minutes=ttl_minutes),
        }
        equity_curve.append(equity)

    if open_position and not price_and_features.empty:
        last_row = price_and_features.iloc[-1]
        close = float(last_row["close"])
        exit_price = close - spread_pips if open_position["direction"] == "long" else close + spread_pips
        risk_distance = open_position["risk_distance"]
        if open_position["direction"] == "long":
            r_multiple = (exit_price - open_position["entry"]) / risk_distance
            pnl = r_multiple * open_position["risk_amount"]
        else:
            r_multiple = (open_position["entry"] - exit_price) / risk_distance
            pnl = r_multiple * open_position["risk_amount"]
        equity += pnl
        risk_state.update_after_trade(r_multiple, risk_settings.streak, base_risk_pct)
        trades.append(
            TradeRecord(
                opened_at=open_position["opened_at"].to_pydatetime(),
                closed_at=price_and_features.index[-1].to_pydatetime(),
                direction=open_position["direction"],
                entry=open_position["entry"],
                exit=exit_price,
                stop=open_position["stop"],
                target=open_position["target"],
                r_multiple=round(float(r_multiple), 4),
                pnl=round(float(pnl), 2),
            )
        )
        equity_curve.append(equity)
        open_position = None

    wins = [t for t in trades if t.r_multiple > 0]
    losses = [t for t in trades if t.r_multiple <= 0]
    pf_all = (sum(t.pnl for t in wins) / abs(sum(t.pnl for t in losses)) if losses else 1.0) if trades else 1.0
    win_rate = len(wins) / len(trades) if trades else 0.0
    avg_r = sum(t.r_multiple for t in trades) / len(trades) if trades else 0.0
    equity_series = pd.Series(equity_curve)
    running_max = equity_series.cummax()
    drawdowns = (equity_series - running_max) / running_max.replace(0, pd.NA)
    max_drawdown = abs(drawdowns.min()) if not drawdowns.empty else 0.0

    base_equity = risk_settings.base_equity
    metrics = {
        "pf_all": round(float(pf_all), 4),
        "win_rate": round(float(win_rate), 4),
        "avg_r": round(float(avg_r), 4),
        "max_drawdown": round(float(max_drawdown), 4),
        "trades": len(trades),
        "start_equity": round(float(base_equity), 2),
        "end_equity": round(float(equity), 2),
    }
    window = {"from": window_from, "to": window_to}
    return PocResult(
        metrics=metrics,
        trades=trades,
        dataset_path=str(dataset_path),
        dataset_hash=dataset_hash,
        window=window,
    )
