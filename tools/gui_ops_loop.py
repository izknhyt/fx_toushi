"""GUI ops automation loop (data update -> signal preview -> CSV export)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "ingestion": self.ingestion,
            "price_csv": self.price_csv,
            "signal_preview": self.signal_preview,
            "signal_csv": self.signal_csv,
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

    return GuiOpsResult(
        ingestion=ingestion_payloads,
        price_csv=price_payloads,
        signal_preview=signal_preview_payload,
        signal_csv=signal_csv_payload,
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
        os.environ.setdefault(key, value)


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
    from tools.signal_preview import _load_manifest_paths
    from src.features.pipeline import FeaturePipeline
    from src.strategies.registry import StrategyManifest

    manifest_paths = _load_manifest_paths(data_manifest)
    if not strategy_manifest.exists():
        return None
    manifest = StrategyManifest.load(strategy_manifest)
    strategy_variants: list[tuple[str, str, int]] = []
    for strategy_id, mode in DONCHIAN_VARIANT_MODES.items():
        entry = manifest.strategies.get(strategy_id)
        if entry is None or not entry.enabled:
            continue
        entry_minutes = _entry_minutes_from_entry(entry)
        strategy_variants.append((strategy_id, mode, entry_minutes))
    if not strategy_variants:
        return {"status": "ok", "appended": 0}

    pipeline = FeaturePipeline.from_config_file(feature_config)
    for symbol in symbols:
        fallback = manifest_paths.get(symbol)
        if fallback:
            curated_path = Path(fallback)
        else:
            curated_path = data_dir / symbol.lower() / f"{symbol.lower()}_m5_latest.parquet"
        if not curated_path.exists():
            continue
        df = pd.read_parquet(curated_path)
        if df.empty:
            continue
        ts_col = "timestamp" if "timestamp" in df.columns else "ts"
        df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
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
    ts_col = "timestamp" if "timestamp" in df.columns else "ts"
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
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

    df = df.copy()
    df[ts_col] = df[ts_col].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    write_header = not output_path.exists()
    df.to_csv(output_path, mode="a", header=write_header, index=False)
    return {
        "status": "ok",
        "symbol": symbol,
        "curated_path": str(curated_path),
        "output_path": str(output_path),
        "appended": int(len(df)),
        "last_ts": df[ts_col].iloc[-1],
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
