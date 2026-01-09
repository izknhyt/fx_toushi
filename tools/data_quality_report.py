"""Generate basic data quality reports for curated market data."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd


def _load_frame(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns:
        raise ValueError(f"missing timestamp in {path}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    df["timestamp"] = df["timestamp"].dt.tz_convert(None)
    return df


def _gap_stats(df: pd.DataFrame, expected_minutes: int) -> dict[str, int]:
    expected = timedelta(minutes=expected_minutes)
    gaps = 0
    max_gap = 0
    ts = df["timestamp"].to_list()
    for prev, curr in zip(ts, ts[1:], strict=False):
        delta = curr - prev
        if delta > expected:
            gaps += 1
            max_gap = max(max_gap, int(delta.total_seconds() // 60))
    return {"gap_count": gaps, "max_gap_minutes": max_gap}


def _null_stats(df: pd.DataFrame) -> dict[str, int]:
    cols = ["open", "high", "low", "close", "volume"]
    return {col: int(df[col].isna().sum()) for col in cols if col in df.columns}


def _basic_stats(df: pd.DataFrame) -> dict[str, float]:
    return {
        "rows": int(len(df)),
        "start": df["timestamp"].min().isoformat() if not df.empty else None,
        "end": df["timestamp"].max().isoformat() if not df.empty else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a data quality report for curated data.")
    parser.add_argument("--symbol", required=True, help="Symbol, e.g. USDJPY")
    parser.add_argument("--path", help="Parquet path (defaults to *_m5_latest.parquet)")
    parser.add_argument(
        "--expected-minutes", type=int, default=5, help="Expected bar interval in minutes"
    )
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    symbol = args.symbol.lower()
    path = (
        Path(args.path)
        if args.path
        else Path(f"data/research/curated/{symbol}/{symbol}_m5_latest.parquet")
    )
    df = _load_frame(path)

    payload = {
        "symbol": symbol.upper(),
        "path": str(path),
        "stats": _basic_stats(df),
        "nulls": _null_stats(df),
        "gaps": _gap_stats(df, args.expected_minutes),
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.write(json.dumps({"output": str(out_path)}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
