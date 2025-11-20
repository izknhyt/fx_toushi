"""Funding CSV loader stub."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict

from .service import FundingCurve


def load_funding_csv(path: str | Path) -> FundingCurve:
    points: Dict[datetime.date, float] = {}
    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            session_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
            points[session_date] = float(row["rate"])
    return FundingCurve(points=points)


__all__ = ["load_funding_csv"]
