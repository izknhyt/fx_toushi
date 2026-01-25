"""Funding CSV loader utilities."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from .service import FundingCurve, SwapRate


@dataclass(slots=True)
class FundingCsvError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


def load_funding_csv(path: str | Path) -> FundingCurve:
    points: dict[date, float] = {}
    swap_rates: dict[str, SwapRate] = {}
    rows = _read_rows(path)
    for row in rows:
        date_value = row.get("date", "")
        rate_value = row.get("rate", "")
        if date_value and rate_value:
            session_date = _parse_date(date_value)
            points[session_date] = _parse_float(rate_value)
            continue
        pair = _normalize_pair(row.get("pair"))
        if not pair:
            raise FundingCsvError("CSV row missing pair")
        if pair in swap_rates:
            raise FundingCsvError(f"Duplicate pair in CSV: {pair}")
        swap_rates[pair] = SwapRate(
            pair=pair,
            swap_long=_parse_float(row.get("swap_long")),
            swap_short=_parse_float(row.get("swap_short")),
            triple_day=_normalize_optional(row.get("triple_day")),
            rollover_time_utc=_normalize_optional(row.get("rollover_time_utc")),
            last_verified_at=_normalize_optional(row.get("last_verified_at")),
            data_source=_normalize_optional(row.get("data_source")),
        )
    return FundingCurve(points=points, swap_rates=swap_rates)


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FundingCsvError(f"Funding CSV not found: {csv_path}")
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for row in reader:
            cleaned: dict[str, str] = {}
            for key, value in row.items():
                if key is None:
                    continue
                cleaned[key.strip().lower()] = (value or "").strip()
            if cleaned:
                rows.append(cleaned)
    if not rows:
        raise FundingCsvError(f"Funding CSV empty: {csv_path}")
    return rows


def _parse_date(value: str) -> date:
    raw = (value or "").strip()
    if not raw:
        raise FundingCsvError("Funding CSV row missing date")
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError as exc:
        raise FundingCsvError(f"Invalid date: {raw}") from exc


def _parse_float(value: str | None) -> float:
    raw = (value or "").strip()
    if not raw:
        raise FundingCsvError("Funding CSV row missing numeric value")
    try:
        return float(raw)
    except ValueError as exc:
        raise FundingCsvError(f"Invalid numeric value: {raw}") from exc


def _normalize_pair(value: str | None) -> str | None:
    raw = (value or "").strip().upper()
    return raw or None


def _normalize_optional(value: str | None) -> str | None:
    raw = (value or "").strip()
    return raw or None


__all__ = ["load_funding_csv", "FundingCsvError"]
