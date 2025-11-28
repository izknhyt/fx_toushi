"""Download Dukascopy tick data, aggregate to OHLCV, and emit a parquet file.

Usage:
    python tools/fetch_dukascopy.py --symbol USDJPY --from 2025-10-01 --to 2025-11-30 --interval 5m

Notes:
    - Downloads hourly tick archives (.bi5) from datafeed.dukascopy.com.
    - Aggregates to the requested interval (default 5m) and saves parquet under
      data/research/curated/<symbol_lower>/<file>.parquet
    - Designed for PoC-scale pulls (weeks〜数ヶ月)。大量取得は要レートリミット/再開処理。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen

import pandas as pd

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
CHUNK_FMT = ">IIfff"  # time, ask, bid, ask_vol, bid_vol
ROW_BYTES = 20


def _fetch_hour(symbol: str, date: dt.datetime) -> bytes | None:
    url = f"{BASE_URL}/{symbol}/{date:%Y/%m/%d/%H}h_ticks.bi5"
    req = Request(url, headers={"User-Agent": "fx-poc-fetcher"})
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception:
        return None


def _parse_bi5(blob: bytes, base_ts: dt.datetime) -> pd.DataFrame:
    data = []
    offset = 0
    while offset + ROW_BYTES <= len(blob):
        (ms, ask, bid, ask_vol, bid_vol) = struct.unpack_from(CHUNK_FMT, blob, offset)
        ts = base_ts + dt.timedelta(milliseconds=ms)
        mid = (ask + bid) / 2
        data.append((ts, mid, ask, bid, ask_vol + bid_vol))
        offset += ROW_BYTES
    if not data:
        return pd.DataFrame(columns=["timestamp", "mid", "ask", "bid", "volume"])
    df = pd.DataFrame(data, columns=["timestamp", "mid", "ask", "bid", "volume"])
    return df


def _iter_hours(start: dt.datetime, end: dt.datetime) -> Iterable[dt.datetime]:
    cursor = start
    while cursor < end:
        yield cursor
        cursor += dt.timedelta(hours=1)


def aggregate(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    df = df.set_index("timestamp")
    rule = interval
    agg = df.resample(rule).agg(
        open=("mid", "first"),
        high=("mid", "max"),
        low=("mid", "min"),
        close=("mid", "last"),
        volume=("volume", "sum"),
    )
    agg = agg.dropna(subset=["open", "high", "low", "close"])
    agg = agg.reset_index()
    return agg


@dataclass
class FetchResult:
    path: Path
    sha256: str
    rows: int
    start: str
    end: str


def fetch_dukascopy(symbol: str, start: dt.datetime, end: dt.datetime, interval: str = "5min") -> FetchResult:
    frames = []
    for hour in _iter_hours(start, end):
        raw = _fetch_hour(symbol, hour)
        if not raw:
            continue
        try:
            import lzma
        except Exception as exc:  # pragma: no cover - defensive
            raise SystemExit(f"Python lzma support missing: {exc}") from exc
        decompressed = lzma.decompress(raw)
        frame = _parse_bi5(decompressed, hour.replace(tzinfo=None))
        if not frame.empty:
            frames.append(frame)
    if not frames:
        raise SystemExit("No data downloaded; check symbol/date range")
    ticks = pd.concat(frames).sort_values("timestamp")
    ohlcv = aggregate(ticks, interval=interval)
    out_dir = Path("data") / "research" / "curated" / symbol.lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    start_str = ohlcv["timestamp"].min().strftime("%Y%m%d")
    end_str = ohlcv["timestamp"].max().strftime("%Y%m%d")
    out_path = out_dir / f"{symbol.lower()}_{interval.replace('min','m')}_{start_str}_{end_str}_dukascopy.parquet"
    ohlcv.to_parquet(out_path, index=False)
    h = hashlib.sha256()
    with open(out_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return FetchResult(
        path=out_path,
        sha256=h.hexdigest(),
        rows=len(ohlcv),
        start=start_str,
        end=end_str,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Dukascopy ticks and aggregate to OHLCV.")
    parser.add_argument("--symbol", default="USDJPY", help="Instrument symbol (e.g., USDJPY)")
    parser.add_argument("--from", dest="date_from", required=True, help="Start date YYYY-MM-DD (UTC)")
    parser.add_argument("--to", dest="date_to", required=True, help="End date YYYY-MM-DD (UTC, exclusive)")
    parser.add_argument("--interval", default="5min", help="Aggregation interval (e.g., 5min, 15min)")
    args = parser.parse_args()

    start = dt.datetime.fromisoformat(args.date_from)
    end = dt.datetime.fromisoformat(args.date_to)
    result = fetch_dukascopy(args.symbol, start, end, interval=args.interval)
    print(
        f"saved={result.path} rows={result.rows} window={result.start}-{result.end} sha256={result.sha256}",
        file=sys.stderr,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
