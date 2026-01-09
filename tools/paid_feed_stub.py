"""Paid feed simulator stub for backtest validation (M1.2 prep)."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import Random


def _utc_iso(ts: datetime) -> str:
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def generate_stub_csv(
    output_path: Path,
    *,
    symbol: str,
    rows: int,
    start: str,
    step_sec: int,
    seed: int,
) -> Path:
    rng = Random(seed)
    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    start_dt = start_dt.astimezone(timezone.utc)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ts", "symbol", "open", "high", "low", "close", "volume", "provider"])
        price = 100.0
        for idx in range(rows):
            ts = start_dt + timedelta(seconds=step_sec * idx)
            drift = rng.uniform(-0.4, 0.4)
            price = max(price + drift, 1.0)
            high = price + rng.uniform(0.0, 0.3)
            low = price - rng.uniform(0.0, 0.3)
            close = price + rng.uniform(-0.2, 0.2)
            volume = int(rng.uniform(100, 1000))
            writer.writerow(
                [
                    _utc_iso(ts),
                    symbol,
                    f"{price:.4f}",
                    f"{high:.4f}",
                    f"{low:.4f}",
                    f"{close:.4f}",
                    volume,
                    "paid_feed_stub",
                ]
            )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Paid feed stub generator")
    parser.add_argument("--out", type=Path, default=Path("data/paid_feed_stub.csv"))
    parser.add_argument("--symbol", type=str, default="USDJPY")
    parser.add_argument("--rows", type=int, default=100)
    parser.add_argument("--start", type=str, default="2025-01-01T00:00:00Z")
    parser.add_argument("--step-sec", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    path = generate_stub_csv(
        args.out,
        symbol=args.symbol,
        rows=args.rows,
        start=args.start,
        step_sec=args.step_sec,
        seed=args.seed,
    )
    print(f"paid_feed_stub: wrote {path}")


if __name__ == "__main__":
    main()
