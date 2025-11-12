"""Quick parity checks for curated parquet datasets used by validation workflows."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def _parse_freq(value: str) -> pd.Timedelta:
    normalised = value.replace("T", "min") if value.endswith("T") else value
    try:
        return pd.to_timedelta(normalised)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise SystemExit(f"Unsupported frequency string: {value}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify curated parquet frequency and continuity.")
    parser.add_argument("parquet_path", type=Path, help="Path to the parquet file to verify")
    parser.add_argument(
        "--expect-frequency",
        default="5T",
        help="Expected pandas-compatible frequency string (default: 5T)",
    )
    args = parser.parse_args()

    if not args.parquet_path.exists():
        raise SystemExit(f"Parquet file not found: {args.parquet_path}")

    df = pd.read_parquet(args.parquet_path)
    if "timestamp" not in df.columns:
        raise SystemExit("Dataset must expose a 'timestamp' column for continuity checks")

    df = df.sort_values("timestamp").reset_index(drop=True)
    deltas = df["timestamp"].diff().dropna()
    expected = _parse_freq(args.expect_frequency)
    mismatches = deltas[deltas != expected]

    start_ts = df["timestamp"].iloc[0]
    end_ts = df["timestamp"].iloc[-1]
    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    summary = {
        "checked_at": now,
        "path": str(args.parquet_path),
        "rows": int(len(df)),
        "window": {"from": str(start_ts), "to": str(end_ts)},
        "expected_frequency": args.expect_frequency,
        "gap_count": int(len(mismatches)),
    }

    print(summary)

    if len(mismatches) > 0:
        raise SystemExit(f"Frequency gaps detected: {len(mismatches)} rows diverge from {expected}")


if __name__ == "__main__":
    main()
