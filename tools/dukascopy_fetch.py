"""
Dukascopy tick downloader and 5m aggregator.

Usage:
    python tools/dukascopy_fetch.py --pair USDJPY --from 2024-01-01 --to 2024-03-31 \\
        --out data/research/curated/usdjpy/usdjpy_m5_20240101_20240331_dukascopy.parquet

Notes:
- Downloads hourly tick files (.bi5) from Dukascopy datafeed, decompresses, and aggregates to
  5m OHLCV (mid-price).
- This script keeps dependencies minimal (requests, pandas) to run in the current repo.
"""

from __future__ import annotations

import argparse
import contextlib
import concurrent.futures
import datetime as dt
import lzma
import struct
import sys
import time
from collections.abc import Iterable
from pathlib import Path

import pandas as pd
import requests


def daterange(start: dt.datetime, end: dt.datetime) -> Iterable[dt.datetime]:
    """Yield hourly datetimes from start to end inclusive."""

    current = start
    while current <= end:
        yield current
        current += dt.timedelta(hours=1)


def fetch_hour(
    pair: str,
    when: dt.datetime,
    *,
    cache_dir: Path | None = None,
    retries: int = 2,
    timeout: int = 30,
    backoff_sec: float = 0.5,
) -> bytes | None:
    """Download a single hour of Dukascopy tick data (.bi5)."""

    url = (
        f"https://datafeed.dukascopy.com/datafeed/{pair.upper()}/"
        f"{when.year:04d}/{when.month - 1:02d}/{when.day:02d}/{when.hour:02d}h_ticks.bi5"
    )
    cache_path = None
    if cache_dir is not None:
        cache_path = (
            cache_dir
            / pair.upper()
            / f"{when.year:04d}"
            / f"{when.month:02d}"
            / f"{when.day:02d}"
            / f"{when.hour:02d}.bi5"
        )
        if cache_path.exists():
            with contextlib.suppress(OSError):
                return cache_path.read_bytes()
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200 and resp.content:
                if cache_path is not None:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    with contextlib.suppress(OSError):
                        cache_path.write_bytes(resp.content)
                return resp.content
            return None
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(max(backoff_sec * (attempt + 1), 0.0))
    _ = last_exc
    return None


def parse_bi5(raw: bytes, base_time: dt.datetime) -> pd.DataFrame:
    """Decode Dukascopy .bi5 tick payload into a DataFrame."""

    if not raw:
        return pd.DataFrame()
    try:
        decompressed = lzma.decompress(raw)
    except Exception:
        return pd.DataFrame()

    records: list[tuple] = []
    tick_size = 20
    for offset in range(0, len(decompressed), tick_size):
        chunk = decompressed[offset : offset + tick_size]
        if len(chunk) < tick_size:
            continue
        (millis, ask_raw, bid_raw, ask_vol, bid_vol) = struct.unpack(">IIIff", chunk)
        ts = base_time + dt.timedelta(milliseconds=millis)
        ask = ask_raw / 1e5
        bid = bid_raw / 1e5
        mid = (ask + bid) / 2
        records.append((ts, mid, ask, bid, ask_vol + bid_vol))

    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records, columns=["timestamp", "mid", "ask", "bid", "volume"])
    df = df.set_index("timestamp").sort_index()
    return df


def aggregate_to_5m(tick_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate tick data to 5m OHLCV (mid price)."""

    if tick_df.empty:
        return pd.DataFrame()
    tick_df = tick_df.copy()
    if tick_df.index.name != "timestamp":
        tick_df.index.name = "timestamp"
    ohlcv = tick_df["mid"].resample("5min").ohlc()
    vol = tick_df["volume"].resample("5min").sum().rename("volume")
    out = ohlcv.join(vol, how="outer").dropna()
    out = out.reset_index().rename(columns=str.lower)
    return out


def aggregate_tick_frames(tick_frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    """Aggregate multiple tick frames to 5m bars without holding all ticks at once."""

    bar_frames: list[pd.DataFrame] = []
    for tick_df in tick_frames:
        if tick_df.empty:
            continue
        bars = aggregate_to_5m(tick_df)
        if not bars.empty:
            bar_frames.append(bars)
    if not bar_frames:
        return pd.DataFrame()
    out = pd.concat(bar_frames, ignore_index=True)
    out = out.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Dukascopy ticks and aggregate to 5m.")
    parser.add_argument("--pair", required=True, help="Symbol, e.g., USDJPY")
    parser.add_argument("--from", dest="date_from", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument(
        "--to", dest="date_to", required=True, help="End date YYYY-MM-DD (inclusive)"
    )
    parser.add_argument("--out", dest="out_path", required=True, help="Output parquet path")
    parser.add_argument(
        "--cache-dir", default="data/cache/dukascopy", help="Cache directory for .bi5"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of hourly fetch workers to use (default: 1)",
    )
    args = parser.parse_args()

    start = dt.datetime.fromisoformat(args.date_from)
    end = dt.datetime.fromisoformat(args.date_to) + dt.timedelta(hours=23)
    cache_dir = Path(args.cache_dir)

    hours = list(daterange(start, end))
    workers = max(int(args.workers), 1)
    tick_frames: list[pd.DataFrame] = []

    def _fetch_and_parse(when: dt.datetime) -> pd.DataFrame:
        raw = fetch_hour(args.pair, when, cache_dir=cache_dir)
        if not raw:
            return pd.DataFrame()
        return parse_bi5(raw, when)

    if workers == 1:
        for idx, when in enumerate(hours, 1):
            df = _fetch_and_parse(when)
            if not df.empty:
                tick_frames.append(df)
            if idx % 48 == 0:
                sys.stdout.write(f"{when} processed ({idx}/{len(hours)})\n")
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(_fetch_and_parse, when): (idx, when)
                for idx, when in enumerate(hours, 1)
            }
            ordered_frames: dict[int, pd.DataFrame] = {}
            for future in concurrent.futures.as_completed(future_map):
                idx, when = future_map[future]
                try:
                    df = future.result()
                except Exception:
                    df = pd.DataFrame()
                if not df.empty:
                    ordered_frames[idx] = df
                if idx % 48 == 0:
                    sys.stdout.write(f"{when} processed ({idx}/{len(hours)})\n")
            tick_frames = [ordered_frames[idx] for idx in sorted(ordered_frames)]

    if not tick_frames:
        sys.stderr.write("No data fetched; nothing to write\n")
        return 1

    bar_df = aggregate_tick_frames(tick_frames)
    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bar_df.to_parquet(out_path, index=False)
    sys.stdout.write(f"Written {len(bar_df)} bars to {out_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
