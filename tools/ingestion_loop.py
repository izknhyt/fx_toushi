"""Minimal ingestion loop for M1 manual operations (dukascopy/yfinance/twelvedata)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from src.core.time_sync import DEFAULT_TIME_SYNC_METRICS, TimeSyncGuard

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@dataclass(slots=True)
class IngestionResult:
    symbol: str
    provider: str
    timeframe: str
    bars: int
    last_bar_ts: str | None
    bar_gap_minutes: int | None
    raw_path: str
    curated_path: str
    fetch_ms: int

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "provider": self.provider,
            "timeframe": self.timeframe,
            "bars": self.bars,
            "last_bar_ts": self.last_bar_ts,
            "bar_gap_minutes": self.bar_gap_minutes,
            "raw_path": self.raw_path,
            "curated_path": self.curated_path,
            "fetch_ms": self.fetch_ms,
        }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_as_of(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _daterange(start: datetime, end: datetime) -> Iterable[datetime]:
    current = start.replace(minute=0, second=0, microsecond=0)
    while current <= end:
        yield current
        current += timedelta(hours=1)


def _fetch_dukascopy_bars(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    from tools.dukascopy_fetch import aggregate_to_5m, fetch_hour, parse_bi5

    frames: list[pd.DataFrame] = []
    for when in _daterange(start, end):
        raw = fetch_hour(symbol, when)
        if not raw:
            continue
        ticks = parse_bi5(raw, when)
        if ticks.empty:
            continue
        bars = aggregate_to_5m(ticks)
        if bars.empty:
            continue
        bars["symbol"] = symbol.upper()
        frames.append(bars)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _normalize_yfinance_symbol(symbol: str) -> str:
    if "=" in symbol:
        return symbol
    if len(symbol) == 6:
        return f"{symbol.upper()}=X"
    return symbol


def _fetch_yfinance_bars(
    symbol: str, start: datetime, end: datetime, *, interval: str
) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("yfinance is not installed; add it to dependencies first") from exc

    ticker = _normalize_yfinance_symbol(symbol)
    df = yf.download(
        tickers=ticker,
        start=start,
        end=end + timedelta(minutes=1),
        interval=interval,
        progress=False,
        auto_adjust=False,
        prepost=False,
        threads=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.reset_index()
    df.columns = [str(col).lower().replace(" ", "_") for col in df.columns]
    rename_map = {
        "datetime": "timestamp",
        "date": "timestamp",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    }
    df = df.rename(columns=rename_map)
    if "timestamp" not in df.columns:
        return pd.DataFrame()
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    df["symbol"] = symbol.upper()
    return df


def _merge_parquet(path: Path, new_df: pd.DataFrame, *, ts_col: str = "timestamp") -> pd.DataFrame:
    if path.exists():
        existing = pd.read_parquet(path)
        merged = pd.concat([existing, new_df], ignore_index=True)
    else:
        merged = new_df.copy()
    if ts_col in merged.columns:
        merged[ts_col] = pd.to_datetime(merged[ts_col], utc=True, errors="coerce")
        merged = merged.dropna(subset=[ts_col]).drop_duplicates(subset=[ts_col]).sort_values(ts_col)
    return merged


def _write_metrics(metrics_path: Path, payload: dict[str, object]) -> None:
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def run_once(
    *,
    symbols: list[str],
    provider: str,
    timeframe: str,
    lookback_hours: int,
    as_of: datetime | None,
    raw_dir: Path,
    curated_dir: Path,
    metrics_path: Path,
    processing_delay_warn_sec: float = 12.0,
) -> list[IngestionResult]:
    from src.core.health import HealthMonitor
    from src.data.quality import DataQualityGuard
    from src.data.service import (
        build_provider_handlers,
        fetch_latest,
        load_provider_sla_thresholds,
        log_processing_delay,
    )

    anchor = as_of or _utcnow()
    results: list[IngestionResult] = []
    guard = DataQualityGuard(expected_timeframe_minutes=5, max_gap_minutes=10)
    health_monitor = HealthMonitor()
    provider_sla = load_provider_sla_thresholds(Path("config") / "provider_sla.yaml")
    start = anchor - timedelta(hours=lookback_hours)
    handlers = build_provider_handlers(timeframe=timeframe, start=_iso(start), end=_iso(anchor))
    fetch_start = time.perf_counter()

    frames = fetch_latest(
        symbols=symbols,
        timeframe=timeframe,
        start=_iso(start),
        end=_iso(anchor),
        provider_priority=[provider] if provider != "auto" else None,
        provider_handlers=handlers,
        metrics_path=metrics_path,
        provider_sla_thresholds=provider_sla,
        data_quality_guard=guard,
        health_monitor=health_monitor,
    )
    elapsed_ms = int((time.perf_counter() - fetch_start) * 1000)

    # Stage: buffer frames before processing to mirror fetch->processing separation.
    frame_queue = deque(frames)
    frame_by_symbol: dict[str, object] = {}
    while frame_queue:
        frame = frame_queue.popleft()
        frame_by_symbol[frame.symbol.upper()] = frame
    for symbol in symbols:
        process_start = time.perf_counter()
        frame = frame_by_symbol.get(symbol.upper())
        bars_df = pd.DataFrame(frame.bars) if frame else pd.DataFrame()
        if bars_df.empty:
            last_ts = None
            bar_gap = None
        else:
            ts_col = (
                "timestamp"
                if "timestamp" in bars_df.columns
                else "ts"
                if "ts" in bars_df.columns
                else None
            )
            last_ts = pd.to_datetime(bars_df[ts_col]).max().to_pydatetime() if ts_col else None
            bar_gap = int((anchor - last_ts).total_seconds() // 60) if last_ts else None
            if bar_gap is not None and bar_gap < 0:
                bar_gap = 0

        symbol_lower = symbol.lower()
        raw_path = (
            raw_dir
            / (provider if provider != "auto" else "auto")
            / symbol_lower
            / f"{anchor.strftime('%Y%m%d')}_m5.parquet"
        )
        curated_path = curated_dir / symbol_lower / f"{symbol_lower}_m5_latest.parquet"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        curated_path.parent.mkdir(parents=True, exist_ok=True)

        if not bars_df.empty:
            merge_col = "timestamp" if "timestamp" in bars_df.columns else "ts"
            merged_raw = _merge_parquet(raw_path, bars_df, ts_col=merge_col)
            merged_raw.to_parquet(raw_path, index=False)
            merged_curated = _merge_parquet(curated_path, bars_df, ts_col=merge_col)
            merged_curated.to_parquet(curated_path, index=False)
        processing_ms = int((time.perf_counter() - process_start) * 1000)

        result = IngestionResult(
            symbol=symbol.upper(),
            provider=provider,
            timeframe=timeframe,
            bars=len(bars_df),
            last_bar_ts=_iso(last_ts),
            bar_gap_minutes=bar_gap,
            raw_path=str(raw_path),
            curated_path=str(curated_path),
            fetch_ms=elapsed_ms,
        )
        results.append(result)

        metrics_payload = {
            "ts": _iso(anchor),
            "provider": provider,
            "phase": "fetch",
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "fetch_p95_ms": elapsed_ms,
            "fetch_p99_ms": elapsed_ms,
            "delay_sec": round(elapsed_ms / 1000.0, 3),
            "fetch_delay_sec": round(elapsed_ms / 1000.0, 3),
            "status": "ok" if not bars_df.empty else "unknown",
            "last_bar_ts": result.last_bar_ts,
            "bar_gap_minutes": result.bar_gap_minutes,
        }
        _write_metrics(metrics_path, metrics_payload)
        log_processing_delay(
            provider=provider,
            timeframe=timeframe,
            symbol=symbol.upper(),
            bars=len(bars_df),
            processing_ms=processing_ms,
            metrics_path=metrics_path,
            health_monitor=health_monitor,
            processing_delay_warn_sec=processing_delay_warn_sec,
            timestamp=_iso(anchor),
        )

    if list(health_monitor.reasons()):
        health_path = Path("snapshots/latest/health_state.json")
        health_path.parent.mkdir(parents=True, exist_ok=True)
        health_path.write_text(
            json.dumps(health_monitor.snapshot().to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return results


def run_loop(
    *,
    symbols: list[str],
    provider: str,
    timeframe: str,
    lookback_hours: int,
    as_of: datetime | None,
    raw_dir: Path,
    curated_dir: Path,
    metrics_path: Path,
    interval_sec: int,
    jitter_sec: int,
    max_iterations: int | None,
    time_sync_interval_sec: int | None,
    time_sync_metrics_path: Path,
) -> None:
    iteration = 0
    last_time_sync = 0.0
    time_sync_guard = TimeSyncGuard() if time_sync_interval_sec else None
    while True:
        results = run_once(
            symbols=symbols,
            provider=provider,
            timeframe=timeframe,
            lookback_hours=lookback_hours,
            as_of=as_of,
            raw_dir=raw_dir,
            curated_dir=curated_dir,
            metrics_path=metrics_path,
        )
        sys.stdout.write(
            json.dumps({"results": [r.as_dict() for r in results]}, ensure_ascii=False) + "\n"
        )
        if time_sync_guard and time_sync_interval_sec:
            now = time.time()
            if now - last_time_sync >= time_sync_interval_sec:
                time_sync_guard.evaluate(
                    metrics_path=time_sync_metrics_path,
                    persist_health_state=True,
                    log_events=True,
                )
                last_time_sync = now
        iteration += 1
        if max_iterations is not None and iteration >= max_iterations:
            break
        sleep_for = max(interval_sec - jitter_sec, 0)
        time.sleep(sleep_for)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run minimal Dukascopy ingestion loop.")
    parser.add_argument(
        "--provider", default="auto", help="Provider name (dukascopy/yfinance/twelvedata/auto)"
    )
    parser.add_argument("--symbols", default="USDJPY", help="Comma-separated symbols")
    parser.add_argument("--timeframe", default="5m", help="Timeframe label")
    parser.add_argument("--lookback-hours", type=int, default=6, help="Lookback window in hours")
    parser.add_argument(
        "--as-of", default=None, help="ISO timestamp to anchor the fetch window (UTC)"
    )
    parser.add_argument("--raw-dir", default="data/raw", help="Raw output root")
    parser.add_argument(
        "--curated-dir", default="data/research/curated", help="Curated output root"
    )
    parser.add_argument(
        "--metrics-path", default="metrics/data_ingestion_sla.jsonl", help="Metrics path"
    )
    parser.add_argument("--interval-sec", type=int, default=300, help="Polling interval seconds")
    parser.add_argument("--jitter-sec", type=int, default=3, help="Sleep jitter seconds")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--max-iterations", type=int, default=None, help="Loop iterations cap")
    parser.add_argument(
        "--time-sync-interval-sec",
        type=int,
        default=600,
        help="Run time sync guard every N seconds (0 to disable)",
    )
    parser.add_argument(
        "--time-sync-metrics-path",
        default=str(DEFAULT_TIME_SYNC_METRICS),
        help="Time sync metrics jsonl path",
    )
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    raw_dir = Path(args.raw_dir)
    curated_dir = Path(args.curated_dir)
    metrics_path = Path(args.metrics_path)
    as_of = parse_as_of(args.as_of)

    if args.once:
        results = run_once(
            symbols=symbols,
            provider=args.provider,
            timeframe=args.timeframe,
            lookback_hours=args.lookback_hours,
            as_of=as_of,
            raw_dir=raw_dir,
            curated_dir=curated_dir,
            metrics_path=metrics_path,
        )
        sys.stdout.write(
            json.dumps({"results": [r.as_dict() for r in results]}, ensure_ascii=False) + "\n"
        )
        return 0

    run_loop(
        symbols=symbols,
        provider=args.provider,
        timeframe=args.timeframe,
        lookback_hours=args.lookback_hours,
        as_of=as_of,
        raw_dir=raw_dir,
        curated_dir=curated_dir,
        metrics_path=metrics_path,
        interval_sec=args.interval_sec,
        jitter_sec=args.jitter_sec,
        max_iterations=args.max_iterations,
        time_sync_interval_sec=args.time_sync_interval_sec or None,
        time_sync_metrics_path=Path(args.time_sync_metrics_path),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
