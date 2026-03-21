from __future__ import annotations

import json
from pathlib import Path

from src.portfolio.multi_pair import (
    choose_default_multi_pair_symbol,
    materialize_multi_pair_data_manifest,
    render_symbol_scoped_value,
    resolve_pair_metadata,
)


def test_resolve_pair_metadata_exposes_symbol_tokens() -> None:
    payload = resolve_pair_metadata("EURUSD")

    assert payload["symbol"] == "EURUSD"
    assert payload["symbol_lower"] == "eurusd"
    assert payload["base"] == "EUR"
    assert payload["quote"] == "USD"


def test_choose_default_multi_pair_symbol_skips_baseline() -> None:
    assert choose_default_multi_pair_symbol(baseline_symbols=["USDJPY"]) == "EURUSD"


def test_render_symbol_scoped_value_formats_pair_tokens() -> None:
    assert (
        render_symbol_scoped_value("{symbol_lower}_breakout_{quote_lower}", symbol="GBPUSD")
        == "gbpusd_breakout_usd"
    )


def test_materialize_multi_pair_data_manifest_adds_watchlist_datasets(tmp_path: Path) -> None:
    eurusd_dir = tmp_path / "data" / "research" / "curated" / "eurusd"
    usdjpy_dir = tmp_path / "data" / "research" / "curated" / "usdjpy"
    eurusd_dir.mkdir(parents=True)
    usdjpy_dir.mkdir(parents=True)
    (eurusd_dir / "eurusd_m5_20220101_20251231_merged.parquet").write_text("x", encoding="utf-8")
    (usdjpy_dir / "usdjpy_m5_20220101_20251231_merged.parquet").write_text("x", encoding="utf-8")

    source = tmp_path / "data_manifest.json"
    source.write_text(
        json.dumps(
            {
                "strategies": {
                    "alpha": {
                        "dataset_path": "baseline.parquet",
                        "dataset_sha256": "abc",
                        "watchlist_datasets": {"USDJPY": {"path": "baseline.parquet", "sha256": "abc"}},
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = materialize_multi_pair_data_manifest(
        source_path=source,
        symbols=["USDJPY", "EURUSD"],
        output_path=tmp_path / "effective.json",
        data_dir=tmp_path / "data" / "research" / "curated",
    )
    payload = json.loads(Path(result["output_path"]).read_text(encoding="utf-8"))

    watchlist = payload["strategies"]["alpha"]["watchlist_datasets"]
    assert result["symbols"] == ["USDJPY", "EURUSD"]
    assert set(watchlist) == {"USDJPY", "EURUSD"}
    assert watchlist["EURUSD"]["path"].endswith("eurusd_m5_20220101_20251231_merged.parquet")
