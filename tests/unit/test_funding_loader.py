from __future__ import annotations

from pathlib import Path

import pytest

from src.funding.loaders import FundingCsvError, load_funding_csv


def test_load_funding_csv_reads_swap_rates(tmp_path: Path) -> None:
    csv_path = tmp_path / "swap_rates.csv"
    csv_path.write_text(
        "\n".join(
            [
                "pair,swap_long,swap_short,triple_day,rollover_time_utc,last_verified_at,data_source",
                "EURUSD,-5.10,1.80,Wed,21:00,2025-03-01T06:00:00Z,manual",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    curve = load_funding_csv(csv_path)

    assert curve.swap_rates["EURUSD"].swap_long == -5.10
    assert curve.swap_rates["EURUSD"].swap_short == 1.80
    assert curve.swap_rates["EURUSD"].triple_day == "Wed"


def test_load_funding_csv_rejects_duplicate_pairs(tmp_path: Path) -> None:
    csv_path = tmp_path / "swap_rates.csv"
    csv_path.write_text(
        "\n".join(
            [
                "pair,swap_long,swap_short",
                "EURUSD,-5.10,1.80",
                "EURUSD,-5.20,1.70",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(FundingCsvError):
        load_funding_csv(csv_path)


def test_load_funding_csv_reads_curve_points(tmp_path: Path) -> None:
    csv_path = tmp_path / "funding_curve.csv"
    csv_path.write_text(
        "\n".join(
            [
                "date,rate",
                "2024-01-02,-0.25",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    curve = load_funding_csv(csv_path)

    assert curve.rate_on(next(iter(curve.points.keys()))) == -0.25


def test_load_funding_csv_allows_empty_date_rate_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "swap_rates.csv"
    csv_path.write_text(
        "\n".join(
            [
                "pair,swap_long,swap_short,date,rate",
                "EURUSD,-5.10,1.80,,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    curve = load_funding_csv(csv_path)

    assert "EURUSD" in curve.swap_rates
