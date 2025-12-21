"""Minimal ingestion loop for M1 manual operations (dukascopy/yfinance)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.dukascopy_fetch import aggregate_to_5m, fetch_hour, parse_bi5


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


def _daterange(start: datetime, end: datetime) -> Iterable[datetime]:
    current = start.replace(minute=0, second=0, microsecond=0)
    while current <= end:
        yield current
        current += timedelta(hours=1)


def _fetch_dukascopy_bars(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
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


def _fetch_yfinance_bars(symbol: str, start: datetime, end: datetime, *, interval: str) -> pd.DataFrame:
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
        merged = merged.drop_duplicates(subset=[ts_col]).sort_values(ts_col)
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
    raw_dir: Path,
    curated_dir: Path,
    metrics_path: Path,
) -> list[IngestionResult]:
    now = _utcnow()
    start = now - timedelta(hours=lookback_hours)
    results: list[IngestionResult] = []

    for symbol in symbols:
        fetch_start = time.perf_counter()
        if provider == "dukascopy":
            bars = _fetch_dukascopy_bars(symbol, start, now)
        elif provider == "yfinance":
            bars = _fetch_yfinance_bars(symbol, start, now, interval="5m")
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        elapsed_ms = int((time.perf_counter() - fetch_start) * 1000)
        if bars.empty:
            last_ts = None
            bar_gap = None
        else:
            last_ts = pd.to_datetime(bars["timestamp"]).max().to_pydatetime()
            bar_gap = int((now - last_ts).total_seconds() // 60)

        symbol_lower = symbol.lower()
        raw_path = raw_dir / provider / symbol_lower / f"{now.strftime('%Y%m%d')}_m5.parquet"
        curated_path = curated_dir / symbol_lower / f"{symbol_lower}_m5_latest.parquet"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        curated_path.parent.mkdir(parents=True, exist_ok=True)

        if not bars.empty:
            merged_raw = _merge_parquet(raw_path, bars)
            merged_raw.to_parquet(raw_path, index=False)
            merged_curated = _merge_parquet(curated_path, bars)
            merged_curated.to_parquet(curated_path, index=False)
        else:
            merged_raw = pd.DataFrame()
            merged_curated = pd.DataFrame()

        result = IngestionResult(
            symbol=symbol.upper(),
            provider=provider,
            timeframe=timeframe,
            bars=len(bars),
            last_bar_ts=_iso(last_ts),
            bar_gap_minutes=bar_gap,
            raw_path=str(raw_path),
            curated_path=str(curated_path),
            fetch_ms=elapsed_ms,
        )
        results.append(result)

        metrics_payload = {
            "ts": _iso(now),
            "provider": provider,
            "phase": "fetch",
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "fetch_p95_ms": elapsed_ms,
            "fetch_p99_ms": elapsed_ms,
            "status": "ok" if bars is not None else "unknown",
            "last_bar_ts": result.last_bar_ts,
            "bar_gap_minutes": result.bar_gap_minutes,
        }
        _write_metrics(metrics_path, metrics_payload)

    return results


def run_loop(
    *,
    symbols: list[str],
    provider: str,
    timeframe: str,
    lookback_hours: int,
    raw_dir: Path,
    curated_dir: Path,
    metrics_path: Path,
    interval_sec: int,
    jitter_sec: int,
    max_iterations: int | None,
) -> None:
    iteration = 0
    while True:
        results = run_once(
            symbols=symbols,
            provider=provider,
            timeframe=timeframe,
            lookback_hours=lookback_hours,
            raw_dir=raw_dir,
            curated_dir=curated_dir,
            metrics_path=metrics_path,
        )
        print(json.dumps({"results": [r.as_dict() for r in results]}, ensure_ascii=False))
        iteration += 1
        if max_iterations is not None and iteration >= max_iterations:
            break
        sleep_for = max(interval_sec - jitter_sec, 0)
        time.sleep(sleep_for)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run minimal Dukascopy ingestion loop.")
    parser.add_argument("--provider", default="dukascopy", help="Provider name (dukascopy)")
    parser.add_argument("--symbols", default="USDJPY", help="Comma-separated symbols")
    parser.add_argument("--timeframe", default="5m", help="Timeframe label")
    parser.add_argument("--lookback-hours", type=int, default=6, help="Lookback window in hours")
    parser.add_argument("--raw-dir", default="data/raw", help="Raw output root")
    parser.add_argument("--curated-dir", default="data/research/curated", help="Curated output root")
    parser.add_argument("--metrics-path", default="metrics/data_ingestion_sla.jsonl", help="Metrics path")
    parser.add_argument("--interval-sec", type=int, default=300, help="Polling interval seconds")
    parser.add_argument("--jitter-sec", type=int, default=3, help="Sleep jitter seconds")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--max-iterations", type=int, default=None, help="Loop iterations cap")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    raw_dir = Path(args.raw_dir)
    curated_dir = Path(args.curated_dir)
    metrics_path = Path(args.metrics_path)

    if args.once:
        results = run_once(
            symbols=symbols,
            provider=args.provider,
            timeframe=args.timeframe,
            lookback_hours=args.lookback_hours,
            raw_dir=raw_dir,
            curated_dir=curated_dir,
            metrics_path=metrics_path,
        )
        print(json.dumps({"results": [r.as_dict() for r in results]}, ensure_ascii=False))
        return 0

    run_loop(
        symbols=symbols,
        provider=args.provider,
        timeframe=args.timeframe,
        lookback_hours=args.lookback_hours,
        raw_dir=raw_dir,
        curated_dir=curated_dir,
        metrics_path=metrics_path,
        interval_sec=args.interval_sec,
        jitter_sec=args.jitter_sec,
        max_iterations=args.max_iterations,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
