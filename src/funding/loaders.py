"""Funding CSV loader stub."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .service import FundingCurve, SwapRate


def load_funding_csv(path: str | Path) -> FundingCurve:
    points: dict[datetime.date, float] = {}
    swap_rates: dict[str, SwapRate] = {}
    with open(path, encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if "date" in row and "rate" in row:
                session_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
                points[session_date] = float(row["rate"])
                continue
            pair = row.get("pair")
            if not pair:
                continue
            swap_rates[pair] = SwapRate(
                pair=pair,
                swap_long=float(row.get("swap_long") or 0.0),
                swap_short=float(row.get("swap_short") or 0.0),
                triple_day=row.get("triple_day"),
                rollover_time_utc=row.get("rollover_time_utc"),
                last_verified_at=row.get("last_verified_at"),
                data_source=row.get("data_source"),
            )
    return FundingCurve(points=points, swap_rates=swap_rates)


__all__ = ["load_funding_csv"]
