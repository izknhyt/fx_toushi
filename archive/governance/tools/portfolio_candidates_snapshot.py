"""Snapshot current candidate trades and admission decisions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.signal_preview import (
    _build_gate_state,
    _candidate_row,
    _diagnose_missing_features,
    _feature_context_for_row,
    _load_available_curated_frames,
    _load_manifest_paths,
    _load_symbols_from_profile,
    _resolve_symbol_dataset_path,
    _candidate_symbol_dataset_paths,
    _utcnow_iso,
)


def run_snapshot(
    *,
    symbols: list[str] | None,
    profile_path: Path,
    data_dir: Path,
    feature_config: Path,
    strategy_manifest: Path,
    data_manifest: Path,
    allocation_config: Path | None = None,
    allocation_profile: str | None = None,
    output_path: Path | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    from src.features.pipeline import FeaturePipeline
    from src.strategies.allocation import StrategyAllocationPolicy
    from src.strategies.plugin_catalog import build_default_plugins
    from src.strategies.registry import StrategyEngine

    profile_symbols = _load_symbols_from_profile(profile_path)
    resolved_symbols = symbols or profile_symbols
    if not resolved_symbols:
        raise SystemExit("No symbols provided. Use --symbols or configure data_ingestion.symbols.")

    pipeline = FeaturePipeline.from_config_file(feature_config)
    engine = StrategyEngine()
    for plugin in build_default_plugins().values():
        engine.register_plugin(plugin)
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
    config_snapshot = type("ConfigSnapshot", (), {"cfg_hash": "portfolio_candidates"})()
    regime = type("RegimeState", (), {"mode": "normal"})()
    account = type("AccountState", (), {"equity": 10_000_000.0})()

    results: dict[str, Any] = {
        "generated_at": _utcnow_iso(),
        "symbols": resolved_symbols,
        "candidates": [],
        "admission_outcomes": [],
        "selected_strategy_ids": [],
        "warnings": [],
        "diagnostics": {},
    }

    manifest_paths = _load_manifest_paths(data_manifest)
    for symbol in resolved_symbols:
        curated_path = _resolve_symbol_dataset_path(
            symbol=symbol,
            data_dir=data_dir,
            manifest_paths=manifest_paths,
        )
        candidate_paths = [
            path
            for path in _candidate_symbol_dataset_paths(
                symbol=symbol,
                data_dir=data_dir,
                manifest_paths=manifest_paths,
            )
            if path.exists()
        ]
        if not candidate_paths:
            results["warnings"].append(f"missing curated data: {curated_path}")
            continue

        frames, load_warnings = _load_available_curated_frames(candidate_paths)
        results["warnings"].extend(load_warnings)
        if not frames:
            continue

        import pandas as pd

        df = pd.concat(frames, ignore_index=True)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        if df.empty:
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
        if verbose:
            results["diagnostics"][symbol] = _diagnose_missing_features(
                combined, required_by_strategy
            )
        else:
            results["diagnostics"][symbol] = diagnostics
        results["selected_strategy_ids"].extend(
            [str(getattr(signal, "strategy_id", "")) for signal in signals if getattr(signal, "strategy_id", None)]
        )
        results["candidates"].extend(engine.last_run_candidate_trades)
        results["admission_outcomes"].extend(engine.last_run_allocation_outcomes)

    resolved_output = output_path or Path("reports") / "portfolio_cli" / "portfolio_candidates_snapshot.json"
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Snapshot current portfolio candidates and admission decisions.")
    parser.add_argument("--symbols", help="Comma-separated symbols (e.g., USDJPY,EURUSD).")
    parser.add_argument("--profile", default="config/profiles/paper.yaml", help="Profile path for defaults.")
    parser.add_argument("--data-dir", default="data/research/curated", help="Curated data root.")
    parser.add_argument("--feature-config", default="config/feature_pipeline.yaml", help="Feature pipeline config.")
    parser.add_argument("--strategy-manifest", default="config/strategy_manifest.yaml", help="Strategy manifest.")
    parser.add_argument("--allocation-config", default=None, help="Optional allocation config.")
    parser.add_argument("--allocation-profile", default=None, help="Allocation profile name.")
    parser.add_argument("--data-manifest", default="reports/data_manifest.json", help="Data manifest for fallbacks.")
    parser.add_argument("--output", help="Optional output JSON path.")
    parser.add_argument("--verbose", action="store_true", help="Print detailed diagnostics")
    args = parser.parse_args()

    symbols = (
        [token.strip().upper() for token in args.symbols.split(",") if token.strip()]
        if args.symbols
        else None
    )
    payload = run_snapshot(
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
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
