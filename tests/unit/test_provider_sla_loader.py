from __future__ import annotations

from pathlib import Path

from src.data.service import load_provider_sla_thresholds


def test_load_provider_sla_thresholds_yaml(tmp_path: Path) -> None:
    path = tmp_path / "provider_sla.yaml"
    path.write_text(
        "schema_version: provider_sla.v1\n"
        "providers:\n"
        "  yfinance:\n"
        "    warn_ms: 1500\n"
        "    breach_ms: 2500\n",
        encoding="utf-8",
    )

    thresholds = load_provider_sla_thresholds(path)

    assert thresholds["yfinance"] == (1500.0, 2500.0)
