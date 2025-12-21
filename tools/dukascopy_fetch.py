"""
Dukascopy tick downloader and 5m aggregator.

Usage:
    python tools/dukascopy_fetch.py --pair USDJPY --from 2024-01-01 --to 2024-03-31 --out data/research/curated/usdjpy/usdjpy_m5_20240101_20240331_dukascopy.parquet

Notes:
- Downloads hourly tick files (.bi5) from Dukascopy datafeed, decompresses, and aggregates to 5m OHLCV (mid-price).
- This script keeps dependencies minimal (requests, pandas) to run in the current repo.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import lzma
import struct
import sys
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import requests


def daterange(start: dt.datetime, end: dt.datetime) -> Iterable[dt.datetime]:
    """Yield hourly datetimes from start to end inclusive."""

    current = start
    while current <= end:
        yield current
        current += dt.timedelta(hours=1)


def fetch_hour(pair: str, when: dt.datetime) -> bytes | None:
    """Download a single hour of Dukascopy tick data (.bi5)."""

    url = (
        f"https://datafeed.dukascopy.com/datafeed/{pair.upper()}/"
        f"{when.year:04d}/{when.month - 1:02d}/{when.day:02d}/{when.hour:02d}h_ticks.bi5"
    )
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200 or not resp.content:
            return None
        return resp.content
    except Exception:
        return None


def parse_bi5(raw: bytes, base_time: dt.datetime) -> pd.DataFrame:
    """Decode Dukascopy .bi5 tick payload into a DataFrame."""

    if not raw:
        return pd.DataFrame()
    try:
        decompressed = lzma.decompress(raw)
    except Exception:
        return pd.DataFrame()

    records: List[tuple] = []
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
    ohlcv = tick_df["mid"].resample("5min").ohlc()
    vol = tick_df["volume"].resample("5min").sum().rename("volume")
    out = ohlcv.join(vol, how="outer").dropna()
    out = out.reset_index().rename(columns=str.lower)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Dukascopy ticks and aggregate to 5m.")
    parser.add_argument("--pair", required=True, help="Symbol, e.g., USDJPY")
    parser.add_argument("--from", dest="date_from", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--out", dest="out_path", required=True, help="Output parquet path")
    args = parser.parse_args()

    start = dt.datetime.fromisoformat(args.date_from)
    end = dt.datetime.fromisoformat(args.date_to) + dt.timedelta(hours=23)

    frames: List[pd.DataFrame] = []
    hours = list(daterange(start, end))
    for idx, when in enumerate(hours, 1):
        raw = fetch_hour(args.pair, when)
        if not raw:
            continue
        df = parse_bi5(raw, when)
        if df.empty:
            continue
        frames.append(df)
        if idx % 48 == 0:
            print(f"{when} processed ({idx}/{len(hours)})")

    if not frames:
        print("No data fetched; nothing to write", file=sys.stderr)
        return 1

    tick_df = pd.concat(frames).sort_index()
    bar_df = aggregate_to_5m(tick_df)
    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bar_df.to_parquet(out_path, index=False)
    print(f"Written {len(bar_df)} bars to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
