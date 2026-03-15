from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from tools.dukascopy_backfill_history import (
    build_history_extension_chunks,
    load_merged_start_date,
    resolve_existing_merged,
)
from tools.dukascopy_fetch import aggregate_tick_frames, aggregate_to_5m


def test_build_history_extension_chunks_splits_range_and_names_outputs(tmp_path: Path) -> None:
    chunks = build_history_extension_chunks(
        symbol="USDJPY",
        target_start=date(2016, 1, 1),
        existing_start=date(2016, 2, 1),
        out_dir=tmp_path,
        chunk_days=14,
    )

    assert [chunk.start for chunk in chunks] == ["2016-01-01", "2016-01-15", "2016-01-29"]
    assert [chunk.end for chunk in chunks] == ["2016-01-14", "2016-01-28", "2016-01-31"]
    assert chunks[0].out_path.endswith("usdjpy_m5_20160101_20160114_dukascopy.parquet")
    assert all(chunk.exists is False for chunk in chunks)


def test_resolve_existing_merged_uses_latest_mtime(tmp_path: Path) -> None:
    symbol_dir = tmp_path / "data" / "research" / "curated" / "usdjpy"
    symbol_dir.mkdir(parents=True)
    older = symbol_dir / "usdjpy_m5_20210101_20250101_merged.parquet"
    newer = symbol_dir / "usdjpy_m5_20210101_20260101_merged.parquet"
    older.write_text("older", encoding="utf-8")
    newer.write_text("newer", encoding="utf-8")
    older.touch()
    newer.touch()

    cwd = Path.cwd()
    try:
        # resolve_existing_merged looks under repo-root data/, so run from tmp_path.
        import os

        os.chdir(tmp_path)
        resolved = resolve_existing_merged("USDJPY")
    finally:
        os.chdir(cwd)

    assert resolved.resolve() == newer.resolve()


def test_load_merged_start_date_reads_earliest_timestamp(tmp_path: Path) -> None:
    merged = tmp_path / "usdjpy_m5_20210101_20210102_merged.parquet"
    pd.DataFrame(
        {
            "timestamp": [
                "2021-01-01T00:00:00Z",
                "2021-01-01T00:05:00Z",
                "2021-01-02T00:00:00Z",
            ]
        }
    ).to_parquet(merged, index=False)

    assert load_merged_start_date(merged) == date(2021, 1, 1)


def test_aggregate_tick_frames_matches_direct_aggregation() -> None:
    index = pd.to_datetime(
        [
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:01:00Z",
            "2024-01-01T00:06:00Z",
            "2024-01-01T01:00:00Z",
            "2024-01-01T01:04:00Z",
            "2024-01-01T01:07:00Z",
        ],
        utc=True,
    )
    tick_df = pd.DataFrame(
        {
            "mid": [150.0, 150.1, 150.2, 150.3, 150.4, 150.5],
            "ask": [150.01, 150.11, 150.21, 150.31, 150.41, 150.51],
            "bid": [149.99, 150.09, 150.19, 150.29, 150.39, 150.49],
            "volume": [1.0, 1.0, 1.5, 1.0, 0.5, 2.0],
        },
        index=index,
    )
    tick_df.index.name = "timestamp"

    first_hour = tick_df[tick_df.index < pd.Timestamp("2024-01-01T01:00:00Z")]
    second_hour = tick_df[tick_df.index >= pd.Timestamp("2024-01-01T01:00:00Z")]

    expected = aggregate_to_5m(tick_df)
    actual = aggregate_tick_frames([first_hour, second_hour])

    pd.testing.assert_frame_equal(actual.reset_index(drop=True), expected.reset_index(drop=True))
