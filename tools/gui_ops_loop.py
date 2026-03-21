"""GUI ops automation loop (data update -> signal preview -> CSV export)."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

import pandas as pd

from src.brokers.fill_shadow import FillShadowStore
from src.interfaces.gui.allocation_surface import summarize_allocation_surface
from src.interfaces.gui.candidate_surface import summarize_candidate_surface
from src.interfaces.gui.shadow_baseline import build_shadow_baseline_summary
from src.interfaces.gui.shadow_daily_ops import build_daily_shadow_ops_summary
from src.interfaces.gui.shadow_daily_review import build_daily_shadow_review_summary
from src.interfaces.gui.shadow_discrepancy_ledger import (
    DEFAULT_DISCREPANCY_LEDGER_PATH,
    build_shadow_baseline_readiness_summary,
    build_shadow_discrepancy_summary,
    load_shadow_discrepancy_ledger,
)
from src.interfaces.gui.shadow_feedback_validation_surface import (
    summarize_shadow_feedback_validation_result,
)
from src.interfaces.gui.shadow_next_stage_surface import summarize_shadow_next_stage_execution
from src.portfolio.shadow_stage_gate import build_shadow_stage_gate_summary
from tools.ingestion_loop import run_once as ingestion_run_once
from tools.signal_preview import run_preview as signal_preview_run

from src.interfaces.cli.signals import export_signals_csv
import os

DONCHIAN_VARIANT_MODES = {
    "m1_baseline_donchian": "bidirectional",
    "m1_baseline_donchian_long_only": "long_only",
    "m1_baseline_donchian_upper_only": "upper_only",
}


@dataclass(slots=True)
class GuiOpsResult:
    ingestion: list[dict[str, Any]]
    price_csv: list[dict[str, Any]]
    signal_preview: dict[str, Any]
    signal_csv: dict[str, Any]
    allocation_summary: dict[str, Any]
    candidate_snapshot: dict[str, Any]
    shadow_baseline_summary: dict[str, Any]
    daily_shadow_review_summary: dict[str, Any]
    shadow_discrepancy_summary: dict[str, Any]
    shadow_readiness_summary: dict[str, Any]
    stage_gate_summary: dict[str, Any]
    soak_summary: dict[str, Any]
    next_stage_execution_template: dict[str, Any]
    shadow_next_stage_execution_state: dict[str, Any]
    shadow_feedback_summary: dict[str, Any]
    shadow_feedback_override_packet: dict[str, Any]
    shadow_feedback_validation_result: dict[str, Any]
    shadow_feedback_rollout_alignment: dict[str, Any]
    shadow_feedback_recovery_packet: dict[str, Any]
    shadow_feedback_recovery_execution_state: dict[str, Any]
    daily_shadow_ops_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ingestion": self.ingestion,
            "price_csv": self.price_csv,
            "signal_preview": self.signal_preview,
            "signal_csv": self.signal_csv,
            "allocation_summary": self.allocation_summary,
            "candidate_snapshot": self.candidate_snapshot,
            "shadow_baseline_summary": self.shadow_baseline_summary,
            "daily_shadow_review_summary": self.daily_shadow_review_summary,
            "shadow_discrepancy_summary": self.shadow_discrepancy_summary,
            "shadow_readiness_summary": self.shadow_readiness_summary,
            "stage_gate_summary": self.stage_gate_summary,
            "soak_summary": self.soak_summary,
            "next_stage_execution_template": self.next_stage_execution_template,
            "shadow_next_stage_execution_state": self.shadow_next_stage_execution_state,
            "shadow_feedback_summary": self.shadow_feedback_summary,
            "shadow_feedback_override_packet": self.shadow_feedback_override_packet,
            "shadow_feedback_validation_result": self.shadow_feedback_validation_result,
            "shadow_feedback_rollout_alignment": self.shadow_feedback_rollout_alignment,
            "shadow_feedback_recovery_packet": self.shadow_feedback_recovery_packet,
            "shadow_feedback_recovery_execution_state": self.shadow_feedback_recovery_execution_state,
            "daily_shadow_ops_summary": self.daily_shadow_ops_summary,
        }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_gui_ops_once(
    *,
    provider: str,
    symbols: list[str],
    timeframe: str,
    lookback_hours: int,
    raw_dir: Path,
    curated_dir: Path,
    metrics_path: Path,
    price_csv_dir: Path,
    bootstrap_rows: int,
    profile_path: Path,
    data_dir: Path,
    feature_config: Path,
    strategy_manifest: Path,
    data_manifest: Path,
    signal_log_path: Path | None,
    backfill_days: int,
    target_r_multiple: float,
    ttl_bars: int,
    trail_atr_mult: float | None,
    spread_pips: float,
    slippage_pips: float,
    slippage_std: float,
    signals_csv_append: bool,
    signals_csv_monthly: bool,
    stage_gate_summary: dict[str, Any] | None = None,
) -> GuiOpsResult:
    _load_dotenv(Path(".env"))
    ingestion_results = ingestion_run_once(
        symbols=symbols,
        provider=provider,
        timeframe=timeframe,
        lookback_hours=lookback_hours,
        as_of=None,
        raw_dir=raw_dir,
        curated_dir=curated_dir,
        metrics_path=metrics_path,
    )
    ingestion_payloads = [result.as_dict() for result in ingestion_results]

    price_payloads: list[dict[str, Any]] = []
    for result in ingestion_results:
        price_payloads.append(
            append_price_csv(
                curated_path=Path(result.curated_path),
                output_dir=price_csv_dir,
                symbol=result.symbol,
                bootstrap_rows=bootstrap_rows,
            )
        )

    _ensure_signal_log(signal_log_path)
    previous_signal_log = _set_signal_log_env(signal_log_path)
    try:
        signal_preview_payload = signal_preview_run(
            symbols=symbols,
            profile_path=profile_path,
            data_dir=data_dir,
            feature_config=feature_config,
            strategy_manifest=strategy_manifest,
            data_manifest=data_manifest,
            output_path=None,
            verbose=False,
        )
    finally:
        _restore_signal_log_env(previous_signal_log)

    try:
        backfill_payload = _backfill_signals(
            symbols=symbols,
            data_dir=data_dir,
            feature_config=feature_config,
            strategy_manifest=strategy_manifest,
            data_manifest=data_manifest,
            signal_log_path=signal_log_path,
            backfill_days=backfill_days,
            target_r_multiple=target_r_multiple,
            ttl_bars=ttl_bars,
            trail_atr_mult=trail_atr_mult,
            spread_pips=spread_pips,
            slippage_pips=slippage_pips,
            slippage_std=slippage_std,
        )
        if backfill_payload:
            signal_preview_payload["backfill"] = backfill_payload
        signal_csv_payload = export_signals_csv(
            input_path=signal_log_path or Path("logs") / "events" / "signal.generated.jsonl",
            append=signals_csv_append,
            monthly=signals_csv_monthly,
        )
    except FileNotFoundError as exc:
        signal_csv_payload = {"status": "missing", "error": str(exc)}
    allocation_summary = _summarize_allocation_decisions(signal_log_path, limit=200)
    candidate_snapshot = (
        summarize_candidate_surface(signal_log_path, limit=200)
        if signal_log_path is not None
        else {"status": "ok", "count": 0, "candidates": []}
    )
    shadow_baseline_summary = build_shadow_baseline_summary(
        allocation_summary=allocation_summary,
        candidate_snapshot=candidate_snapshot,
    )
    shadow_next_stage_execution_state = summarize_shadow_next_stage_execution()
    daily_shadow_review_summary = build_daily_shadow_review_summary(
        allocation_summary=allocation_summary,
        candidate_snapshot=candidate_snapshot,
        fill_store=FillShadowStore(),
        broker_shadow_event_log=Path("logs/broker/shadow_events.jsonl"),
        shadow_next_stage_execution_state=shadow_next_stage_execution_state,
        history_path=Path("reports/analysis/shadow/daily_shadow_review_history.jsonl"),
        discrepancy_ledger_path=DEFAULT_DISCREPANCY_LEDGER_PATH,
        stage_gate_summary=stage_gate_summary,
    )
    discrepancy_ledger = load_shadow_discrepancy_ledger(DEFAULT_DISCREPANCY_LEDGER_PATH)
    shadow_discrepancy_summary = build_shadow_discrepancy_summary(daily_shadow_review_summary, discrepancy_ledger)
    shadow_readiness_summary = build_shadow_baseline_readiness_summary(
        daily_shadow_review_summary,
        shadow_discrepancy_summary,
    )
    daily_shadow_review_summary["discrepancy_summary"] = shadow_discrepancy_summary
    daily_shadow_review_summary["shadow_readiness_summary"] = shadow_readiness_summary
    if stage_gate_summary is None:
        daily_shadow_review_summary["stage_gate_summary"] = build_shadow_stage_gate_summary(
            daily_shadow_review_summary
        )
    else:
        daily_shadow_review_summary["stage_gate_summary"] = dict(stage_gate_summary)
    daily_shadow_ops_summary = build_daily_shadow_ops_summary(
        daily_shadow_review_summary,
        focused_validation_output_dir=Path("reports/analysis/shadow/feedback_validation"),
        rollout_history_path=Path("reports/analysis/shadow/shadow_feedback_rollout_history.jsonl"),
        recovery_ledger_path=Path("logs/ops/shadow_feedback_recovery.jsonl"),
        candidate_onboarding_output_dir=Path("reports/analysis/shadow/candidate_onboarding"),
    )
    shadow_feedback_validation_result = (
        dict(daily_shadow_ops_summary.get("shadow_feedback_validation_result") or {})
        if isinstance(daily_shadow_ops_summary.get("shadow_feedback_validation_result"), Mapping)
        else summarize_shadow_feedback_validation_result()
    )

    return GuiOpsResult(
        ingestion=ingestion_payloads,
        price_csv=price_payloads,
        signal_preview=signal_preview_payload,
        signal_csv=signal_csv_payload,
        allocation_summary=allocation_summary,
        candidate_snapshot=candidate_snapshot,
        shadow_baseline_summary=shadow_baseline_summary,
        daily_shadow_review_summary=daily_shadow_review_summary,
        shadow_discrepancy_summary=shadow_discrepancy_summary,
        shadow_readiness_summary=shadow_readiness_summary,
        stage_gate_summary=dict(daily_shadow_review_summary.get("stage_gate_summary") or {}),
        soak_summary=dict(daily_shadow_review_summary.get("soak_summary") or {}),
        next_stage_execution_template=dict(daily_shadow_review_summary.get("next_stage_execution_template") or {}),
        shadow_next_stage_execution_state=shadow_next_stage_execution_state,
        shadow_feedback_summary=dict(daily_shadow_review_summary.get("shadow_feedback_summary") or {}),
        shadow_feedback_override_packet=dict(daily_shadow_ops_summary.get("shadow_feedback_override_packet") or {}),
        shadow_feedback_validation_result=shadow_feedback_validation_result,
        shadow_feedback_rollout_alignment=dict(daily_shadow_ops_summary.get("shadow_feedback_rollout_alignment") or {}),
        shadow_feedback_recovery_packet=dict(daily_shadow_ops_summary.get("shadow_feedback_recovery_packet") or {}),
        shadow_feedback_recovery_execution_state=dict(
            daily_shadow_ops_summary.get("shadow_feedback_recovery_execution_state") or {}
        ),
        daily_shadow_ops_summary=daily_shadow_ops_summary,
    )


def run_gui_ops_loop(
    *,
    provider: str,
    symbols: list[str],
    timeframe: str,
    lookback_hours: int,
    raw_dir: Path,
    curated_dir: Path,
    metrics_path: Path,
    price_csv_dir: Path,
    bootstrap_rows: int,
    profile_path: Path,
    data_dir: Path,
    feature_config: Path,
    strategy_manifest: Path,
    data_manifest: Path,
    signal_log_path: Path | None,
    backfill_days: int,
    target_r_multiple: float,
    ttl_bars: int,
    trail_atr_mult: float | None,
    spread_pips: float,
    slippage_pips: float,
    slippage_std: float,
    interval_sec: int,
    once: bool,
    max_iterations: int | None,
    signals_csv_append: bool,
    signals_csv_monthly: bool,
    stage_gate_summary: dict[str, Any] | None = None,
) -> list[GuiOpsResult] | None:
    if not once and max_iterations is None:
        while True:
            run_gui_ops_once(
                provider=provider,
                symbols=symbols,
                timeframe=timeframe,
                lookback_hours=lookback_hours,
                raw_dir=raw_dir,
                curated_dir=curated_dir,
                metrics_path=metrics_path,
                price_csv_dir=price_csv_dir,
                bootstrap_rows=bootstrap_rows,
                profile_path=profile_path,
                data_dir=data_dir,
                feature_config=feature_config,
                strategy_manifest=strategy_manifest,
                data_manifest=data_manifest,
                signal_log_path=signal_log_path,
                backfill_days=backfill_days,
                target_r_multiple=target_r_multiple,
                ttl_bars=ttl_bars,
                trail_atr_mult=trail_atr_mult,
                spread_pips=spread_pips,
                slippage_pips=slippage_pips,
                slippage_std=slippage_std,
                signals_csv_append=signals_csv_append,
                signals_csv_monthly=signals_csv_monthly,
                stage_gate_summary=stage_gate_summary,
            )
            time.sleep(interval_sec)
        return None

    results: list[GuiOpsResult] = []
    iteration = 0
    while True:
        iteration += 1
        results.append(
            run_gui_ops_once(
                provider=provider,
                symbols=symbols,
                timeframe=timeframe,
                lookback_hours=lookback_hours,
                raw_dir=raw_dir,
                curated_dir=curated_dir,
                metrics_path=metrics_path,
                price_csv_dir=price_csv_dir,
                bootstrap_rows=bootstrap_rows,
                profile_path=profile_path,
                data_dir=data_dir,
                feature_config=feature_config,
                strategy_manifest=strategy_manifest,
                data_manifest=data_manifest,
                signal_log_path=signal_log_path,
                backfill_days=backfill_days,
                target_r_multiple=target_r_multiple,
                ttl_bars=ttl_bars,
                trail_atr_mult=trail_atr_mult,
                spread_pips=spread_pips,
                slippage_pips=slippage_pips,
                slippage_std=slippage_std,
                signals_csv_append=signals_csv_append,
                signals_csv_monthly=signals_csv_monthly,
                stage_gate_summary=stage_gate_summary,
            )
        )
        if once:
            break
        if max_iterations is not None and iteration >= max_iterations:
            break
        time.sleep(interval_sec)
    return results


def _set_signal_log_env(signal_log_path: Path | None) -> str | None:
    if signal_log_path is None:
        return None
    prev = os.getenv("TRADECTL_SIGNAL_EVENT_LOG")
    os.environ["TRADECTL_SIGNAL_EVENT_LOG"] = str(signal_log_path)
    return prev


def _restore_signal_log_env(previous: str | None) -> None:
    if previous is None:
        os.environ.pop("TRADECTL_SIGNAL_EVENT_LOG", None)
        return
    os.environ["TRADECTL_SIGNAL_EVENT_LOG"] = previous


def _ensure_signal_log(signal_log_path: Path | None) -> None:
    if signal_log_path is None:
        return
    signal_log_path.parent.mkdir(parents=True, exist_ok=True)
    if not signal_log_path.exists():
        signal_log_path.touch()


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if not key:
            continue
        current = os.getenv(key)
        if current is None or current == "":
            os.environ[key] = value


def _entry_minutes_from_entry(entry: Any) -> int:
    entry_params = entry.parameters.get("entry", {}) if hasattr(entry, "parameters") else {}
    timeframe = str(entry_params.get("timeframe", "5m"))
    return _timeframe_to_minutes(timeframe)


def _timeframe_to_minutes(value: str) -> int:
    text = value.strip().lower()
    if text.endswith("m"):
        try:
            return int(text[:-1])
        except ValueError:
            return 5
    if text.endswith("h"):
        try:
            return int(text[:-1]) * 60
        except ValueError:
            return 60
    if text.endswith("d"):
        try:
            return int(text[:-1]) * 60 * 24
        except ValueError:
            return 1440
    return 5


def _backfill_signals(
    *,
    symbols: list[str],
    data_dir: Path,
    feature_config: Path,
    strategy_manifest: Path,
    data_manifest: Path,
    signal_log_path: Path | None,
    backfill_days: int,
    target_r_multiple: float,
    ttl_bars: int,
    trail_atr_mult: float | None,
    spread_pips: float,
    slippage_pips: float,
    slippage_std: float,
) -> dict[str, Any] | None:
    if signal_log_path is None:
        return None
    last_ts = _read_last_signal_ts(signal_log_path)
    if last_ts is None and backfill_days <= 0:
        return None
    start_ts = last_ts + timedelta(seconds=1) if last_ts else None
    if backfill_days > 0:
        cutoff = _utcnow() - timedelta(days=backfill_days)
        start_ts = max(start_ts, cutoff) if start_ts else cutoff

    records: list[dict[str, Any]] = []
    from tools.signal_preview import (
        _build_gate_state,
        _candidate_symbol_dataset_paths,
        _feature_context_for_row,
        _load_available_curated_frames,
        _load_manifest_paths,
    )
    from src.features.pipeline import FeaturePipeline
    from src.strategies.plugin_catalog import build_default_plugins
    from src.strategies.registry import StrategyEngine, StrategyManifest

    manifest_paths = _load_manifest_paths(data_manifest)
    if not strategy_manifest.exists():
        return None
    manifest = StrategyManifest.load(strategy_manifest)
    enabled_strategy_ids = [strategy_id for strategy_id, _ in manifest.enabled_strategies()]
    non_donchian_strategy_ids = {
        strategy_id for strategy_id in enabled_strategy_ids if strategy_id not in DONCHIAN_VARIANT_MODES
    }

    history_engine: StrategyEngine | None = None
    history_manifest = None
    if non_donchian_strategy_ids:
        # Backfill replays use run_all() per historical row; route internal signal logs to
        # os.devnull so we only append normalized GUI backfill payloads once.
        previous_signal_log = os.getenv("TRADECTL_SIGNAL_EVENT_LOG")
        os.environ["TRADECTL_SIGNAL_EVENT_LOG"] = os.devnull
        try:
            history_engine = StrategyEngine()
            for plugin in build_default_plugins().values():
                history_engine.register_plugin(plugin)
            history_manifest = history_engine.load_manifest(strategy_manifest)
        finally:
            if previous_signal_log is None:
                os.environ.pop("TRADECTL_SIGNAL_EVENT_LOG", None)
            else:
                os.environ["TRADECTL_SIGNAL_EVENT_LOG"] = previous_signal_log

    strategy_variants: list[tuple[str, str, int]] = []
    for strategy_id, mode in DONCHIAN_VARIANT_MODES.items():
        entry = manifest.strategies.get(strategy_id)
        if entry is None or not entry.enabled:
            continue
        entry_minutes = _entry_minutes_from_entry(entry)
        strategy_variants.append((strategy_id, mode, entry_minutes))
    if not strategy_variants and history_engine is None:
        return {"status": "ok", "appended": 0}

    pipeline = FeaturePipeline.from_config_file(feature_config)
    for symbol in symbols:
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
            continue
        frames, _load_warnings = _load_available_curated_frames(candidate_paths)
        if not frames:
            continue
        df = pd.concat(frames, ignore_index=True)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        ts_col, parsed_ts = _resolve_time_column(df)
        if ts_col is None or parsed_ts is None:
            continue
        df[ts_col] = parsed_ts
        df = df.dropna(subset=[ts_col]).sort_values(ts_col)
        features = pipeline.compute_feature_matrix(symbol=symbol, price_df=df)
        if features.empty:
            continue
        combined = df.set_index(ts_col).join(features, how="left")
        if start_ts is not None:
            combined = combined.loc[combined.index >= start_ts]
        if combined.empty:
            continue
        for strategy_id, mode, entry_minutes in strategy_variants:
            entry = manifest.strategies.get(strategy_id)
            params = entry.parameters if entry is not None else {}
            entry_params = params.get("entry") if isinstance(params, dict) else {}
            filters = (
                entry_params.get("filters") if isinstance(entry_params, dict) else {}
            )
            execution = params.get("execution") if isinstance(params, dict) else {}
            records.extend(
                _detect_breakouts(
                    combined,
                    symbol,
                    strategy_id=strategy_id,
                    mode=mode,
                    entry_minutes=entry_minutes,
                    target_r_multiple=target_r_multiple,
                    ttl_bars=ttl_bars,
                    trail_atr_mult=trail_atr_mult,
                    spread_pips=spread_pips,
                    slippage_pips=slippage_pips,
                    slippage_std=slippage_std,
                    filters=filters if isinstance(filters, dict) else None,
                    execution=execution if isinstance(execution, dict) else None,
                )
            )

        if history_engine is not None and history_manifest is not None:
            gate = _build_gate_state([symbol])
            account = SimpleNamespace(equity=10_000_000)
            config_snapshot = SimpleNamespace(cfg_hash="gui_backfill")
            regime = SimpleNamespace(mode="normal")
            for strategy_id, entry in history_manifest.enabled_strategies():
                entry.watchlist = (symbol,)
                plugin = history_engine._plugins.get(strategy_id)
                if plugin is not None:
                    entry.metadata.required_features = tuple(plugin.metadata.required_features)
            strategy_params_by_id: dict[str, Mapping[str, Any]] = {}
            for strategy_id, entry in history_manifest.enabled_strategies():
                params = entry.parameters if isinstance(entry.parameters, Mapping) else {}
                strategy_params_by_id[strategy_id] = params if isinstance(params, Mapping) else {}
            for _, row in combined.iterrows():
                context, clock = _feature_context_for_row(pipeline, [symbol], row)
                try:
                    signals = history_engine.run_all(
                        features=context,
                        regime=regime,
                        gate=gate,
                        account=account,
                        config=config_snapshot,
                        clock=clock,
                        watchlist=[symbol],
                        seed=0,
                    )
                except Exception:
                    continue
                for signal in signals:
                    strategy_id = str(getattr(signal, "strategy_id", "") or "")
                    if strategy_id not in non_donchian_strategy_ids:
                        continue
                    records.append(
                        _engine_signal_payload(
                            signal=signal,
                            ts=row.name,
                            symbol=symbol,
                            row=row,
                            strategy_parameters=strategy_params_by_id.get(strategy_id),
                            default_target_r_multiple=target_r_multiple,
                            default_ttl_bars=ttl_bars,
                            default_trail_atr_mult=trail_atr_mult,
                            default_spread_pips=spread_pips,
                            default_slippage_pips=slippage_pips,
                            default_slippage_std=slippage_std,
                        )
                    )

    if not records:
        return {"status": "ok", "appended": 0}
    records.sort(key=lambda item: item.get("ts") or "")
    with signal_log_path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
    return {
        "status": "ok",
        "appended": len(records),
        "start_ts": start_ts.isoformat().replace("+00:00", "Z") if start_ts else None,
    }


def _summarize_allocation_decisions(
    signal_log_path: Path | None,
    *,
    limit: int,
) -> dict[str, Any]:
    if signal_log_path is None or not signal_log_path.exists():
        return {
            "status": "ok",
            "count": 0,
            "summary": {"accept": 0, "reject": 0, "defer": 0, "resize": 0, "replace": 0},
            "recent": [],
            "portfolio_surface": {
                "active_slots": {"count": 0, "slots": []},
                "portfolio_group_occupancy": [],
                "exposure_bucket_occupancy": [],
            },
        }

    payload = summarize_allocation_surface(signal_log_path, limit=limit)
    decisions = payload.get("decisions")
    recent = decisions[-5:] if isinstance(decisions, list) else []
    return {
        "status": payload.get("status", "ok"),
        "count": payload.get("count", 0),
        "summary": payload.get("summary", {}),
        "reason_summary": payload.get("reason_summary", []),
        "conflict_summary": payload.get("conflict_summary", []),
        "winner_conflict_summary": payload.get("winner_conflict_summary", []),
        "winner_bias_summary": payload.get("winner_bias_summary", []),
        "winner_review_summary": payload.get("winner_review_summary", []),
        "recent": recent,
        "portfolio_surface": payload.get("portfolio_surface", {}),
    }


def _detect_breakouts(
    combined: pd.DataFrame,
    symbol: str,
    *,
    strategy_id: str,
    mode: str,
    entry_minutes: int,
    target_r_multiple: float,
    ttl_bars: int,
    trail_atr_mult: float | None,
    spread_pips: float,
    slippage_pips: float,
    slippage_std: float,
    filters: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    required_cols = {
        "donchian_upper20_1h",
        "donchian_lower20_1h",
        "donchian_mid20_1h",
        "close_5m",
        "atr_14_1h",
    }
    if not required_cols.issubset(combined.columns):
        return []
    upper = combined["donchian_upper20_1h"]
    lower = combined["donchian_lower20_1h"]
    mid = combined["donchian_mid20_1h"]
    close = combined["close_5m"]
    atr = combined["atr_14_1h"]
    trend = combined["regime_trend_1h"] if "regime_trend_1h" in combined.columns else None
    buffer = (atr * 0.02).clip(lower=0.05)
    price_close = combined["close"] if "close" in combined.columns else close

    valid = ~(upper.isna() | lower.isna() | close.isna() | atr.isna())
    if valid.empty:
        return []
    hours = combined.index.tz_convert(timezone.utc).hour
    session_ok = (hours >= 6) & (hours <= 21)
    valid = valid & session_ok

    breakout_upper = (close > (upper + buffer)) & valid
    breakout_lower = (close < (lower - buffer)) & valid

    def _resolve_direction(breakout: str) -> str | None:
        if mode == "upper_only":
            return "long" if breakout == "upper" else None
        if mode == "long_only":
            return "long"
        return "long" if breakout == "upper" else "short"

    filters = filters or {}
    execution = execution or {}
    spread_cost = _coerce_float(execution.get("spread")) or spread_pips
    slippage_cost = _coerce_float(execution.get("slippage")) or slippage_pips

    records: list[dict[str, Any]] = []
    for ts in breakout_upper[breakout_upper].index:
        direction = _resolve_direction("upper")
        if direction is None:
            continue
        filter_payload = _evaluate_breakout_filters(
            direction=direction,
            ts=ts,
            close_price=float(close.loc[ts]),
            level=float(upper.loc[ts]),
            atr_value=float(atr.loc[ts]),
            trend_series=trend,
            filters=filters,
            spread_cost=spread_cost,
            slippage_cost=slippage_cost,
        )
        if not filter_payload["ok"]:
            continue
        records.append(
            _signal_payload(
                ts=ts,
                strategy_id=strategy_id,
                symbol=symbol,
                breakout="upper",
                direction=direction,
                level=float(upper.loc[ts]),
                buffer=float(buffer.loc[ts]),
                rationale="breakout_upper",
                close_price=float(price_close.loc[ts]),
                entry_minutes=entry_minutes,
                target_r_multiple=target_r_multiple,
                ttl_bars=ttl_bars,
                trail_atr_mult=trail_atr_mult,
                spread_pips=spread_cost,
                slippage_pips=slippage_cost,
                slippage_std=slippage_std,
                breakout_width=filter_payload["breakout_width"],
                filter_flags=filter_payload["filter_flags"],
                quality_score=filter_payload["quality_score"],
            )
        )
    for ts in breakout_lower[breakout_lower].index:
        direction = _resolve_direction("lower")
        if direction is None:
            continue
        filter_payload = _evaluate_breakout_filters(
            direction=direction,
            ts=ts,
            close_price=float(close.loc[ts]),
            level=float(lower.loc[ts]),
            atr_value=float(atr.loc[ts]),
            trend_series=trend,
            filters=filters,
            spread_cost=spread_cost,
            slippage_cost=slippage_cost,
        )
        if not filter_payload["ok"]:
            continue
        records.append(
            _signal_payload(
                ts=ts,
                strategy_id=strategy_id,
                symbol=symbol,
                breakout="lower",
                direction=direction,
                level=float(lower.loc[ts]),
                buffer=float(buffer.loc[ts]),
                rationale="breakout_lower",
                close_price=float(price_close.loc[ts]),
                entry_minutes=entry_minutes,
                target_r_multiple=target_r_multiple,
                ttl_bars=ttl_bars,
                trail_atr_mult=trail_atr_mult,
                spread_pips=spread_cost,
                slippage_pips=slippage_cost,
                slippage_std=slippage_std,
                breakout_width=filter_payload["breakout_width"],
                filter_flags=filter_payload["filter_flags"],
                quality_score=filter_payload["quality_score"],
            )
        )
    return records


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except Exception:
        return None


def _normalize_close_price_for_symbol(close_price: float | None, symbol: str) -> float | None:
    if close_price is None or not math.isfinite(close_price) or close_price <= 0:
        return None

    normalized = symbol.upper().strip()
    if len(normalized) == 6 and normalized.isalpha():
        if normalized.endswith("JPY"):
            low, high = 50.0, 300.0
        else:
            low, high = 0.2, 5.0
    else:
        low, high = 0.01, 100_000.0
    target = math.sqrt(low * high)
    candidates = (0.0002, 0.001, 0.002, 0.01, 0.1, 1.0, 10.0, 100.0)

    best_value = close_price
    best_score = float("inf")
    for factor in candidates:
        scaled = close_price * factor
        if scaled <= 0 or not math.isfinite(scaled):
            continue
        distance = abs(math.log(scaled / target))
        if low <= scaled <= high:
            score = distance
        elif scaled < low:
            score = abs(math.log(low / scaled)) + 5.0
        else:
            score = abs(math.log(scaled / high)) + 5.0
        if score < best_score:
            best_score = score
            best_value = scaled
    return best_value


def _evaluate_breakout_filters(
    *,
    direction: str,
    ts: datetime,
    close_price: float,
    level: float,
    atr_value: float,
    trend_series: pd.Series | None,
    filters: dict[str, Any],
    spread_cost: float,
    slippage_cost: float,
) -> dict[str, Any]:
    breakout_width = abs(close_price - level)
    filter_flags: dict[str, bool] = {}
    quality_score = None
    ok = True

    trend_required = bool(filters.get("trend_required"))
    trend_threshold = _coerce_float(filters.get("trend_threshold")) or 0.0
    if trend_required:
        if trend_series is None or ts not in trend_series.index:
            filter_flags["trend_ok"] = False
            ok = False
        else:
            trend_value = _coerce_float(trend_series.loc[ts])
            if trend_value is None:
                filter_flags["trend_ok"] = False
                ok = False
            elif direction == "long":
                filter_flags["trend_ok"] = trend_value > trend_threshold
                ok = ok and filter_flags["trend_ok"]
            else:
                filter_flags["trend_ok"] = trend_value < -trend_threshold
                ok = ok and filter_flags["trend_ok"]

    atr_min = _coerce_float(filters.get("atr_min"))
    if atr_min is not None:
        filter_flags["atr_ok"] = atr_value >= atr_min
        ok = ok and filter_flags["atr_ok"]

    min_breakout_abs = _coerce_float(filters.get("min_breakout_abs"))
    breakout_min_atr_mult = _coerce_float(filters.get("breakout_min_atr_mult"))
    breakout_min_cost_mult = _coerce_float(filters.get("breakout_min_cost_mult"))

    thresholds: list[float] = []
    if min_breakout_abs is not None:
        thresholds.append(min_breakout_abs)
    if breakout_min_atr_mult is not None:
        thresholds.append(breakout_min_atr_mult * atr_value)
    if breakout_min_cost_mult is not None:
        cost = spread_cost + slippage_cost
        if cost > 0:
            thresholds.append(breakout_min_cost_mult * cost)

    if thresholds:
        threshold = max(thresholds)
        filter_flags["breakout_quality_ok"] = breakout_width >= threshold
        if threshold > 0:
            quality_score = breakout_width / threshold
        ok = ok and filter_flags["breakout_quality_ok"]

    return {
        "ok": ok,
        "breakout_width": breakout_width,
        "filter_flags": filter_flags or None,
        "quality_score": quality_score,
    }


def _signal_payload(
    *,
    ts: datetime,
    strategy_id: str,
    symbol: str,
    breakout: str,
    direction: str,
    level: float,
    buffer: float,
    rationale: str,
    close_price: float,
    entry_minutes: int,
    target_r_multiple: float,
    ttl_bars: int,
    trail_atr_mult: float | None,
    spread_pips: float,
    slippage_pips: float,
    slippage_std: float,
    breakout_width: float | None = None,
    filter_flags: dict[str, bool] | None = None,
    quality_score: float | None = None,
) -> dict[str, Any]:
    scaled_close = _normalize_close_price_for_symbol(close_price, symbol)
    if (
        scaled_close is not None
        and close_price > 0
        and math.isfinite(close_price)
        and math.isfinite(scaled_close)
    ):
        scale_factor = scaled_close / close_price
        close_price = scaled_close
        level = level * scale_factor
        buffer = buffer * scale_factor
        if breakout_width is not None:
            breakout_width = breakout_width * abs(scale_factor)

    if direction == "long":
        entry_price = close_price + spread_pips + slippage_pips
        stop_price = level - buffer
        risk_distance = abs(entry_price - stop_price)
        target_price = entry_price + target_r_multiple * risk_distance
    else:
        entry_price = close_price - spread_pips - slippage_pips
        stop_price = level + buffer
        risk_distance = abs(entry_price - stop_price)
        target_price = entry_price - target_r_multiple * risk_distance
    expire_at = ts + timedelta(minutes=entry_minutes * ttl_bars)
    return {
        "event": "signal.generated",
        "ts": ts.isoformat().replace("+00:00", "Z"),
        "status": "generated",
        "reason": None,
        "strategy_id": strategy_id,
        "feature_flags": {},
        "seed": 0,
        "watchlist": [symbol],
        "symbol": symbol,
        "direction": direction,
        "confidence": None,
        "rationale": rationale,
        "breakout": breakout,
        "level": level,
        "buffer": buffer,
        "breakout_width": breakout_width,
        "filter_flags": filter_flags,
        "quality_score": quality_score,
        "entry": entry_price,
        "stop": stop_price,
        "target": target_price,
        "expire_at": expire_at.isoformat().replace("+00:00", "Z"),
        "ttl_bars": ttl_bars,
        "entry_timeframe_minutes": entry_minutes,
        "target_r_multiple": target_r_multiple,
        "trail_atr_mult": trail_atr_mult,
        "spread_pips": spread_pips,
        "slippage_pips": slippage_pips,
        "slippage_std": slippage_std,
        "score": None,
        "badges": None,
    }


def _engine_signal_payload(
    *,
    signal: Any,
    ts: datetime,
    symbol: str,
    row: pd.Series,
    strategy_parameters: Mapping[str, Any] | None,
    default_target_r_multiple: float,
    default_ttl_bars: int,
    default_trail_atr_mult: float | None,
    default_spread_pips: float,
    default_slippage_pips: float,
    default_slippage_std: float,
) -> dict[str, Any]:
    strategy_id = str(getattr(signal, "strategy_id", "") or "")
    direction = str(getattr(signal, "direction", "") or "").lower() or None
    confidence = _coerce_float(getattr(signal, "confidence", None))
    rationale = str(getattr(signal, "rationale", "") or "")
    score = _coerce_float(getattr(signal, "score", None))
    quality_score = _coerce_float(getattr(signal, "quality_score", None))
    level = _coerce_float(getattr(signal, "level", None))
    buffer = _coerce_float(getattr(signal, "buffer", None))
    breakout = getattr(signal, "breakout", None)
    breakout_width = _coerce_float(getattr(signal, "breakout_width", None))
    filter_flags = getattr(signal, "filter_flags", None)
    params = strategy_parameters if isinstance(strategy_parameters, Mapping) else {}
    entry_cfg = params.get("entry") if isinstance(params, Mapping) else {}
    sizing_cfg = params.get("sizing") if isinstance(params, Mapping) else {}
    execution_cfg = params.get("execution") if isinstance(params, Mapping) else {}
    entry_cfg = entry_cfg if isinstance(entry_cfg, Mapping) else {}
    sizing_cfg = sizing_cfg if isinstance(sizing_cfg, Mapping) else {}
    execution_cfg = execution_cfg if isinstance(execution_cfg, Mapping) else {}

    close_price = _coerce_float(row.get("close_5m"))
    if close_price is None:
        close_price = _coerce_float(row.get("close"))
    close_price = _normalize_close_price_for_symbol(close_price, symbol)
    if close_price is not None and close_price > 1000:
        close_price = None
    atr_value = _coerce_float(row.get("atr_14_1h")) or 0.08
    atr_sl_mult = _coerce_float(sizing_cfg.get("atr_sl_mult")) or 1.0
    target_r = _coerce_float(sizing_cfg.get("tp_r_multiple")) or default_target_r_multiple
    ttl_value = int(sizing_cfg.get("ttl_bars") or default_ttl_bars or 1)
    ttl_value = max(1, ttl_value)
    timeframe = str(entry_cfg.get("timeframe", "5m"))
    entry_minutes = max(1, _timeframe_to_minutes(timeframe))
    spread_cost = _coerce_float(execution_cfg.get("spread")) or default_spread_pips
    slippage_cost = _coerce_float(execution_cfg.get("slippage")) or default_slippage_pips
    slippage_std = _coerce_float(execution_cfg.get("slippage_std")) or default_slippage_std

    risk_distance = 0.01
    entry_price = None
    stop_price = None
    target_price = None
    expire_at = None
    if close_price is not None and direction in {"long", "short"}:
        raw_risk_distance = max(atr_value * max(0.1, atr_sl_mult), 0.0)
        min_risk_distance = max(close_price * 0.0002, 0.0005)
        max_risk_distance = max(close_price * 0.02, min_risk_distance)
        risk_distance = min(max(raw_risk_distance, min_risk_distance), max_risk_distance)
        if direction == "long":
            entry_price = close_price + spread_cost + slippage_cost
            stop_price = entry_price - risk_distance
            target_price = entry_price + target_r * risk_distance
        else:
            entry_price = close_price - spread_cost - slippage_cost
            stop_price = entry_price + risk_distance
            target_price = entry_price - target_r * risk_distance
        expire_at = (ts + timedelta(minutes=entry_minutes * ttl_value)).isoformat().replace("+00:00", "Z")
        if level is None:
            level = entry_price
        if buffer is None:
            buffer = risk_distance

    return {
        "event": "signal.generated",
        "ts": ts.isoformat().replace("+00:00", "Z"),
        "status": "generated",
        "reason": None,
        "strategy_id": strategy_id,
        "feature_flags": {},
        "seed": 0,
        "watchlist": [symbol],
        "symbol": symbol,
        "direction": direction,
        "confidence": confidence,
        "rationale": rationale,
        "breakout": breakout,
        "level": level,
        "buffer": buffer,
        "breakout_width": breakout_width,
        "filter_flags": filter_flags,
        "quality_score": quality_score,
        "entry": entry_price,
        "stop": stop_price,
        "target": target_price,
        "expire_at": expire_at,
        "ttl_bars": ttl_value,
        "entry_timeframe_minutes": entry_minutes,
        "target_r_multiple": target_r,
        "trail_atr_mult": _coerce_float(sizing_cfg.get("atr_sl_mult")) or default_trail_atr_mult,
        "spread_pips": spread_cost,
        "slippage_pips": slippage_cost,
        "slippage_std": slippage_std,
        "score": score,
        "badges": None,
    }


def _read_last_signal_ts(path: Path) -> datetime | None:
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines[-5000:]):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = payload.get("ts")
        parsed = _parse_ts(ts)
        if parsed is not None:
            return parsed
    return None


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_time_column(df: pd.DataFrame) -> tuple[str | None, pd.Series | None]:
    for candidate in ("timestamp", "ts"):
        if candidate not in df.columns:
            continue
        parsed = pd.to_datetime(df[candidate], utc=True, errors="coerce")
        if parsed.notna().any():
            return candidate, parsed
    return None, None


def append_price_csv(
    *,
    curated_path: Path,
    output_dir: Path,
    symbol: str,
    bootstrap_rows: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{symbol.lower()}_m5.csv"
    if not curated_path.exists():
        return {
            "status": "missing",
            "symbol": symbol,
            "curated_path": str(curated_path),
            "output_path": str(output_path),
            "appended": 0,
        }

    df = pd.read_parquet(curated_path)
    if df.empty:
        return {
            "status": "empty",
            "symbol": symbol,
            "curated_path": str(curated_path),
            "output_path": str(output_path),
            "appended": 0,
        }
    ts_col, parsed_ts = _resolve_time_column(df)
    if ts_col is None or parsed_ts is None:
        return {
            "status": "empty",
            "symbol": symbol,
            "curated_path": str(curated_path),
            "output_path": str(output_path),
            "appended": 0,
        }
    df[ts_col] = parsed_ts
    df = df.dropna(subset=[ts_col]).sort_values(ts_col)

    last_ts = _read_last_csv_ts(output_path)
    if last_ts is not None:
        df = df[df[ts_col] > last_ts]
    elif bootstrap_rows > 0:
        df = df.tail(bootstrap_rows)

    if df.empty:
        return {
            "status": "ok",
            "symbol": symbol,
            "curated_path": str(curated_path),
            "output_path": str(output_path),
            "appended": 0,
        }

    required = ["open", "high", "low", "close"]
    missing_required = [column for column in required if column not in df.columns]
    if missing_required:
        return {
            "status": "empty",
            "symbol": symbol,
            "curated_path": str(curated_path),
            "output_path": str(output_path),
            "appended": 0,
        }

    df = df.copy()
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df = df[[ts_col, "open", "high", "low", "close", "volume"]].rename(
        columns={ts_col: "timestamp"}
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    if df.empty:
        return {
            "status": "ok",
            "symbol": symbol,
            "curated_path": str(curated_path),
            "output_path": str(output_path),
            "appended": 0,
        }
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    write_header = not output_path.exists()
    df.to_csv(output_path, mode="a", header=write_header, index=False)
    return {
        "status": "ok",
        "symbol": symbol,
        "curated_path": str(curated_path),
        "output_path": str(output_path),
        "appended": int(len(df)),
        "last_ts": df["timestamp"].iloc[-1],
        "generated_at": _utcnow_iso(),
    }


def _read_last_csv_ts(path: Path) -> datetime | None:
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return None
    last_line = None
    for line in reversed(lines):
        if line.strip():
            last_line = line
            break
    if not last_line:
        return None
    headers = lines[0].split(",")
    values = last_line.split(",")
    if len(values) != len(headers):
        return None
    row = dict(zip(headers, values))
    ts_value = row.get("timestamp") or row.get("ts")
    if not ts_value:
        return None
    text = ts_value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
