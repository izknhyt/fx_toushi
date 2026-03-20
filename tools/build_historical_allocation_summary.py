"""Build allocation-summary evidence from historical candidate/admission events."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from tools.signal_preview import (
    _build_gate_state,
    _feature_context_for_row,
    _load_curated_frame,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_allocation_surface_summarizer():
    module_path = PROJECT_ROOT / "src" / "interfaces" / "gui" / "allocation_surface.py"
    spec = importlib.util.spec_from_file_location("allocation_surface_for_tools", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - loader creation failure is exceptional
        raise RuntimeError(f"could not load allocation surface helper: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.summarize_allocation_surface


def _usable_mask(
    frame: pd.DataFrame,
    required_by_strategy: Mapping[str, frozenset[str]],
) -> pd.Series:
    usable = pd.Series(False, index=frame.index)
    for required in required_by_strategy.values():
        required_cols = [column for column in required if column in frame.columns]
        if len(required_cols) != len(required) or not required_cols:
            continue
        usable = usable | frame[required_cols].notna().all(axis=1)
    return usable


def synthesize_admission_records(
    *,
    ts: str,
    symbol: str,
    candidate_trades: Iterable[Mapping[str, Any]],
    admission_outcomes: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidate_by_strategy: dict[str, dict[str, Any]] = {}
    for candidate in candidate_trades:
        strategy_id = str(candidate.get("strategy_id") or "").strip()
        if strategy_id:
            candidate_by_strategy[strategy_id] = dict(candidate)

    records: list[dict[str, Any]] = []
    for outcome in admission_outcomes:
        strategy_id = str(outcome.get("strategy_id") or "").strip()
        candidate = candidate_by_strategy.get(strategy_id, {})
        record = {
            "event": "portfolio.admission",
            "ts": ts,
            "strategy_id": strategy_id or None,
            "symbol": str(candidate.get("symbol") or symbol).strip().upper() or None,
            "status": outcome.get("decision"),
            "reason": outcome.get("reason_code") or outcome.get("reason"),
            "candidate_id": candidate.get("candidate_id"),
            "candidate": candidate,
            "allocation_decision": dict(outcome),
        }
        side = candidate.get("side")
        if side:
            record["direction"] = side
        confidence = candidate.get("confidence")
        if confidence is not None:
            record["confidence"] = confidence
            record["score"] = confidence
        quality_score = candidate.get("quality_score")
        if quality_score is not None:
            record["quality_score"] = quality_score
        records.append(record)
    return records


def build_historical_summary(
    *,
    symbol: str,
    data_path: Path,
    feature_config: Path,
    strategy_manifest: Path,
    allocation_config: Path,
    allocation_profile: str,
    start: str | None,
    end: str | None,
    stride: int,
    output_json: Path,
    output_md: Path | None,
) -> dict[str, Any]:
    from src.features.pipeline import FeaturePipeline
    from src.strategies.allocation import StrategyAllocationPolicy
    from src.strategies.plugin_catalog import build_default_plugins
    from src.strategies.registry import StrategyEngine

    pipeline = FeaturePipeline.from_config_file(feature_config)
    engine = StrategyEngine()
    for plugin in build_default_plugins().values():
        engine.register_plugin(plugin)
    manifest = engine.load_manifest(strategy_manifest)
    engine.set_allocation_policy(
        StrategyAllocationPolicy.load(allocation_config, profile=allocation_profile)
    )

    required_by_strategy = {
        strategy_id: entry.metadata.required_feature_set
        for strategy_id, entry in manifest.enabled_strategies()
    }
    for strategy_id, entry in manifest.enabled_strategies():
        entry.watchlist = (symbol,)
        plugin = engine._plugins.get(strategy_id)
        if plugin is not None:
            entry.metadata.required_features = tuple(plugin.metadata.required_features)

    frame = _load_curated_frame(data_path)
    if start:
        start_ts = pd.Timestamp(start, tz="UTC")
        frame = frame.loc[frame["timestamp"] >= start_ts]
    if end:
        end_ts = pd.Timestamp(end, tz="UTC")
        frame = frame.loc[frame["timestamp"] <= end_ts]
    frame = frame.reset_index(drop=True)
    feature_matrix = pipeline.compute_feature_matrix(symbol=symbol, price_df=frame)
    combined = frame.set_index("timestamp").join(feature_matrix, how="left")
    combined = combined.loc[_usable_mask(combined, required_by_strategy)]
    if stride > 1:
        combined = combined.iloc[::stride]

    gate = _build_gate_state([symbol])
    regime = SimpleNamespace(mode="normal")
    config_snapshot = SimpleNamespace(cfg_hash="historical_allocation_summary")
    account = SimpleNamespace(equity=10_000_000.0, positions=[])

    records: list[dict[str, Any]] = []
    rows_evaluated = 0
    rows_with_outcomes = 0
    candidate_count = 0
    for ts, row in combined.iterrows():
        rows_evaluated += 1
        context, clock = _feature_context_for_row(pipeline, [symbol], row)
        engine.run_all(
            features=context,
            regime=regime,
            gate=gate,
            account=account,
            config=config_snapshot,
            clock=clock,
            watchlist=[symbol],
            seed=0,
        )
        outcomes = list(engine.last_run_allocation_outcomes)
        if not outcomes:
            continue
        candidates = list(engine.last_run_candidate_trades)
        candidate_count += len(candidates)
        rows_with_outcomes += 1
        records.extend(
            synthesize_admission_records(
                ts=pd.Timestamp(ts).tz_convert("UTC").isoformat().replace("+00:00", "Z"),
                symbol=symbol,
                candidate_trades=candidates,
                admission_outcomes=outcomes,
            )
        )

    summarize = _load_allocation_surface_summarizer()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False) as handle:
        temp_path = Path(handle.name)
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    try:
        summary = summarize(temp_path, limit=max(len(records), 1))
    finally:
        temp_path.unlink(missing_ok=True)

    payload = {
        "generated_at_utc": _utcnow_iso(),
        "symbol": symbol,
        "data_path": str(data_path),
        "feature_config": str(feature_config),
        "strategy_manifest": str(strategy_manifest),
        "allocation_config": str(allocation_config),
        "allocation_profile": allocation_profile,
        "start": start,
        "end": end,
        "stride": stride,
        "rows_evaluated": rows_evaluated,
        "rows_with_outcomes": rows_with_outcomes,
        "candidate_count": candidate_count,
        "admission_event_count": len(records),
        **summary,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_summary_md(payload), encoding="utf-8")
    return payload


def render_summary_md(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Historical Allocation Summary",
        "",
        f"- generated_at_utc: `{payload.get('generated_at_utc')}`",
        f"- symbol: `{payload.get('symbol')}`",
        f"- start: `{payload.get('start')}`",
        f"- end: `{payload.get('end')}`",
        f"- stride: `{payload.get('stride')}`",
        f"- rows_evaluated: `{payload.get('rows_evaluated')}`",
        f"- rows_with_outcomes: `{payload.get('rows_with_outcomes')}`",
        f"- admission_event_count: `{payload.get('admission_event_count')}`",
        "",
        "| Winner | Share % | Count | Action | Top Reason |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in payload.get("winner_review_summary", []):
        lines.append(
            "| "
            + f"{row.get('winner_strategy_id')} | "
            + f"{row.get('share_pct')} | "
            + f"{row.get('count')} | "
            + f"{row.get('suggested_action')} | "
            + f"{row.get('top_reason_code')} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build historical allocation summary evidence from candidate/admission events."
    )
    parser.add_argument("--symbol", default="USDJPY")
    parser.add_argument("--data-path", type=Path, required=True)
    parser.add_argument("--feature-config", type=Path, default=PROJECT_ROOT / "config/feature_pipeline.yaml")
    parser.add_argument("--strategy-manifest", type=Path, default=PROJECT_ROOT / "config/strategy_manifest.parallel_portfolio_v2.yaml")
    parser.add_argument("--allocation-config", type=Path, default=PROJECT_ROOT / "config/strategy_allocation.yaml")
    parser.add_argument("--allocation-profile", default="portfolio_admission_v2")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--stride", type=int, default=12)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()

    payload = build_historical_summary(
        symbol=str(args.symbol).strip().upper(),
        data_path=args.data_path,
        feature_config=args.feature_config,
        strategy_manifest=args.strategy_manifest,
        allocation_config=args.allocation_config,
        allocation_profile=args.allocation_profile,
        start=args.start,
        end=args.end,
        stride=max(1, int(args.stride)),
        output_json=args.output_json,
        output_md=args.output_md,
    )
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
