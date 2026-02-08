"""Preview signals from the latest curated market data.

Loads the latest curated parquet per symbol, computes feature columns, and
evaluates enabled strategies against the most recent usable bar.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pandas as pd
import yaml

if TYPE_CHECKING:
    from src.features.pipeline import FeaturePipeline


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_symbols_from_profile(path: Path) -> list[str]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    symbols = payload.get("data_ingestion", {}).get("symbols", [])
    return [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]


def _load_manifest_paths(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else {}
    strategies = payload.get("strategies", {})
    paths: dict[str, str] = {}
    for entry in strategies.values():
        for symbol, dataset in (entry.get("watchlist_datasets") or {}).items():
            dataset_path = dataset.get("path")
            if dataset_path:
                paths[str(symbol).upper()] = str(dataset_path)
    return paths


def _build_gate_state(symbols: Iterable[str]) -> SimpleNamespace:
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
    return SimpleNamespace(market=market, risk=risk, human=human, schema_version="preview")


def _load_curated_frame(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns:
        raise ValueError(f"Missing 'timestamp' column in {path}")
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp").reset_index(drop=True)


def _feature_context_for_row(
    pipeline: FeaturePipeline, symbols: Iterable[str], row: pd.Series
) -> tuple[Any, SimpleNamespace]:
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
        determinism=context.determinism,
        _store=store,
    )
    clock = SimpleNamespace(now=row.name.to_pydatetime(), timeframe="5m")
    return context, clock


def _candidate_row(
    frame: pd.DataFrame, required_by_strategy: dict[str, frozenset[str]]
) -> tuple[pd.Series | None, dict[str, list[str]]]:
    best_row = None
    best_ts = None
    diagnostics: dict[str, list[str]] = {}
    for strategy_id, required in required_by_strategy.items():
        cols = [col for col in required if col in frame.columns]
        missing_cols = sorted(set(required) - set(cols))
        if missing_cols:
            diagnostics[strategy_id] = missing_cols
            continue
        candidate = frame.dropna(subset=cols)
        if candidate.empty:
            diagnostics[strategy_id] = cols
            continue
        row = candidate.iloc[-1]
        ts = row.name
        if best_ts is None or ts > best_ts:
            best_ts = ts
            best_row = row
    return best_row, diagnostics


def _collect_signal_payload(signal: Any) -> dict[str, Any]:
    payload = {
        "strategy_id": getattr(signal, "strategy_id", None),
        "symbol": getattr(signal, "symbol", None),
        "direction": getattr(signal, "direction", None),
        "confidence": getattr(signal, "confidence", None),
        "rationale": getattr(signal, "rationale", None),
    }
    return payload


def _diagnose_missing_features(
    combined: pd.DataFrame,
    required_by_strategy: dict[str, frozenset[str]],
) -> dict[str, dict[str, Any]]:
    diagnostics: dict[str, dict[str, Any]] = {}
    for strategy_id, required in required_by_strategy.items():
        present = [col for col in required if col in combined.columns]
        missing = sorted(set(required) - set(present))
        if missing:
            diagnostics[strategy_id] = {
                "status": "missing_columns",
                "missing": missing,
            }
            continue
        null_counts = {col: int(combined[col].isna().sum()) for col in present}
        diagnostics[strategy_id] = {
            "status": "ok",
            "null_counts": null_counts,
            "last_row_nulls": [col for col in present if pd.isna(combined.iloc[-1][col])],
        }
    return diagnostics


def _format_signal_summary(signals: list[dict[str, Any]]) -> list[str]:
    summary: list[str] = []
    for signal in signals:
        strategy_id = signal.get("strategy_id")
        symbol = signal.get("symbol")
        direction = signal.get("direction")
        confidence = signal.get("confidence")
        summary.append(f"{symbol} {strategy_id} {direction} conf={confidence}")
    return summary


def run_preview(
    *,
    symbols: list[str] | None,
    profile_path: Path,
    data_dir: Path,
    feature_config: Path,
    strategy_manifest: Path,
    data_manifest: Path,
    allocation_config: Path | None = None,
    allocation_profile: str | None = None,
    output_path: Path | None,
    verbose: bool,
) -> dict[str, Any]:
    profile_symbols = _load_symbols_from_profile(profile_path)
    resolved_symbols = symbols or profile_symbols
    if not resolved_symbols:
        raise SystemExit("No symbols provided. Use --symbols or configure data_ingestion.symbols.")

    from src.features.pipeline import FeaturePipeline
    from src.strategies.donchian import (
        DonchianBreakoutLongOnlyStrategy,
        DonchianBreakoutStrategy,
        DonchianBreakoutUpperOnlyStrategy,
    )
    from src.strategies.ma_rsi import MovingAverageRsiStrategy
    from src.strategies.us_session_momentum import UsSessionTrendPullbackStrategy
    from src.strategies.allocation import StrategyAllocationPolicy
    from src.strategies.registry import StrategyEngine

    pipeline = FeaturePipeline.from_config_file(feature_config)
    engine = StrategyEngine()
    engine.register_plugin(MovingAverageRsiStrategy())
    engine.register_plugin(DonchianBreakoutStrategy())
    engine.register_plugin(DonchianBreakoutLongOnlyStrategy())
    engine.register_plugin(DonchianBreakoutUpperOnlyStrategy())
    engine.register_plugin(UsSessionTrendPullbackStrategy())
    manifest = engine.load_manifest(strategy_manifest)
    if allocation_config and allocation_config.exists():
        engine.set_allocation_policy(
            StrategyAllocationPolicy.load(
                allocation_config,
                profile=allocation_profile,
            )
        )

    required_by_strategy = {
        strategy_id: entry.metadata.required_feature_set
        for strategy_id, entry in manifest.enabled_strategies()
    }
    gate = _build_gate_state(resolved_symbols)
    account = SimpleNamespace(equity=10_000_000)
    config_snapshot = SimpleNamespace(cfg_hash="signal_preview")
    regime = SimpleNamespace(mode="normal")

    results: dict[str, Any] = {
        "generated_at": _utcnow_iso(),
        "symbols": resolved_symbols,
        "signals": [],
        "warnings": [],
        "diagnostics": {},
    }

    manifest_paths = _load_manifest_paths(data_manifest)
    for symbol in resolved_symbols:
        fallback = manifest_paths.get(symbol)
        if fallback:
            curated_path = Path(fallback)
        else:
            curated_path = data_dir / symbol.lower() / f"{symbol.lower()}_m5_latest.parquet"
        if not curated_path.exists():
            results["warnings"].append(f"missing curated data: {curated_path}")
            continue

        df = _load_curated_frame(curated_path)
        if df.empty:
            results["warnings"].append(f"empty dataset: {curated_path}")
            continue

        feature_matrix = pipeline.compute_feature_matrix(symbol=symbol, price_df=df)
        if feature_matrix.empty:
            results["warnings"].append(f"feature matrix empty: {symbol}")
            continue

        combined = df.set_index("timestamp").join(feature_matrix, how="left")
        row, diagnostics = _candidate_row(combined, required_by_strategy)
        if row is None:
            results["warnings"].append(f"no usable row with required features: {symbol}")
            if verbose:
                results["diagnostics"][symbol] = _diagnose_missing_features(
                    combined, required_by_strategy
                )
            else:
                results["diagnostics"][symbol] = diagnostics
            continue

        context, clock = _feature_context_for_row(pipeline, [symbol], row)
        for strategy_id, entry in manifest.enabled_strategies():
            entry.watchlist = (symbol,)
            plugin = engine._plugins.get(strategy_id)
            if plugin is not None:
                entry.metadata.required_features = tuple(plugin.metadata.required_features)
        signals = engine.run_all(
            features=context,
            regime=regime,
            gate=gate,
            account=account,
            config=config_snapshot,
            clock=clock,
            watchlist=[symbol],
            seed=0,
        )
        if not signals:
            results["warnings"].append(f"no signals emitted: {symbol}")
        if verbose:
            results["diagnostics"][symbol] = _diagnose_missing_features(
                combined, required_by_strategy
            )
        else:
            results["diagnostics"][symbol] = diagnostics
        results["signals"].extend([_collect_signal_payload(signal) for signal in signals])

    resolved_output = output_path or Path("reports") / "signal_preview" / f"{_utcnow_iso()}.json"
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    summary: dict[str, Any] = {
        "output": str(resolved_output),
        "signals": len(results["signals"]),
        "warnings": results["warnings"],
    }
    if verbose:
        summary["signal_summary"] = _format_signal_summary(results["signals"])
    return summary


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    parser = argparse.ArgumentParser(description="Preview strategy signals from curated data.")
    parser.add_argument("--symbols", help="Comma-separated symbols (e.g., USDJPY,EURUSD).")
    parser.add_argument(
        "--profile", default="config/profiles/paper.yaml", help="Profile path for defaults."
    )
    parser.add_argument("--data-dir", default="data/research/curated", help="Curated data root.")
    parser.add_argument(
        "--feature-config", default="config/feature_pipeline.yaml", help="Feature pipeline config."
    )
    parser.add_argument(
        "--strategy-manifest", default="config/strategy_manifest.yaml", help="Strategy manifest."
    )
    parser.add_argument(
        "--allocation-config",
        default=None,
        help="Optional allocation config (e.g. config/strategy_allocation.yaml).",
    )
    parser.add_argument(
        "--allocation-profile",
        default=None,
        help="Allocation profile name in allocation config.",
    )
    parser.add_argument(
        "--data-manifest", default="reports/data_manifest.json", help="Data manifest for fallbacks."
    )
    parser.add_argument("--output", help="Optional output JSON path.")
    parser.add_argument("--verbose", action="store_true", help="Print detailed diagnostics")
    args = parser.parse_args()

    symbols = (
        [token.strip().upper() for token in args.symbols.split(",") if token.strip()]
        if args.symbols
        else None
    )
    summary = run_preview(
        symbols=symbols,
        profile_path=Path(args.profile),
        data_dir=Path(args.data_dir),
        feature_config=Path(args.feature_config),
        strategy_manifest=Path(args.strategy_manifest),
        data_manifest=Path(args.data_manifest),
        allocation_config=Path(args.allocation_config) if args.allocation_config else None,
        allocation_profile=args.allocation_profile,
        output_path=Path(args.output) if args.output else None,
        verbose=args.verbose,
    )
    sys.stdout.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
