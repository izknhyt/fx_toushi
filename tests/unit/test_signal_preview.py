from pathlib import Path

import pandas as pd

from tools.signal_preview import (
    _candidate_symbol_dataset_paths,
    _load_available_curated_frames,
    _load_curated_frame,
    _resolve_symbol_dataset_path,
)


def _write_dataset(path: Path, timestamps: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [1.0] * len(timestamps),
            "high": [1.0] * len(timestamps),
            "low": [1.0] * len(timestamps),
            "close": [1.0] * len(timestamps),
            "volume": [1.0] * len(timestamps),
        }
    ).to_parquet(path, index=False)


def test_resolve_symbol_dataset_path_prefers_newer_latest_file(tmp_path: Path) -> None:
    symbol = "USDJPY"
    data_dir = tmp_path / "data/research/curated"
    fallback = data_dir / "usdjpy" / "usdjpy_m5_latest.parquet"
    manifest_path = tmp_path / "data/research/curated/usdjpy_m5_clean/usdjpy_old.parquet"

    _write_dataset(manifest_path, ["2022-01-07T21:50:00Z", "2022-01-07T21:55:00Z"])
    _write_dataset(fallback, ["2025-12-19T21:50:00Z", "2025-12-19T21:55:00Z"])

    resolved = _resolve_symbol_dataset_path(
        symbol=symbol,
        data_dir=data_dir,
        manifest_paths={symbol: str(manifest_path)},
    )
    assert resolved == fallback


def test_load_curated_frame_falls_back_to_ts_column(tmp_path: Path) -> None:
    dataset = tmp_path / "data/research/curated/usdjpy/usdjpy_m5_latest.parquet"
    dataset.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "timestamp": [None, None],
            "ts": ["2026-02-09T09:20:00Z", "2026-02-09T09:25:00Z"],
            "open": [150.1, 150.2],
            "high": [150.2, 150.3],
            "low": [150.0, 150.1],
            "close": [150.15, 150.25],
            "volume": [100.0, 120.0],
        }
    ).to_parquet(dataset, index=False)

    frame = _load_curated_frame(dataset)
    assert len(frame) == 2
    assert "timestamp" in frame.columns
    assert frame["timestamp"].iloc[-1].isoformat() == "2026-02-09T09:25:00+00:00"


def test_candidate_symbol_dataset_paths_includes_manifest_and_latest(tmp_path: Path) -> None:
    data_dir = tmp_path / "data/research/curated"
    manifest = tmp_path / "data/research/curated/usdjpy_m5_clean/usdjpy_old.parquet"
    merged = data_dir / "usdjpy" / "usdjpy_m5_20220101_20241231_merged.parquet"
    _write_dataset(merged, ["2026-02-09T09:20:00Z", "2026-02-09T09:25:00Z"])
    paths = _candidate_symbol_dataset_paths(
        symbol="USDJPY",
        data_dir=data_dir,
        manifest_paths={"USDJPY": str(manifest)},
    )
    assert paths[0] == manifest
    assert paths[1] == merged
    assert paths[2] == data_dir / "usdjpy" / "usdjpy_m5_latest.parquet"


def test_load_available_curated_frames_skips_invalid_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.parquet"
    pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]}).to_parquet(
        bad,
        index=False,
    )
    good = tmp_path / "good.parquet"
    _write_dataset(good, ["2026-02-09T09:20:00Z", "2026-02-09T09:25:00Z"])

    frames, warnings = _load_available_curated_frames([bad, good])

    assert len(frames) == 1
    assert "invalid curated data:" in warnings[0]


def test_candidate_symbol_dataset_paths_symbol_root_includes_latest(tmp_path: Path) -> None:
    symbol = "USDJPY"
    symbol_root = tmp_path / "data/research/curated/usdjpy"
    merged = symbol_root / "usdjpy_m5_20240101_20240131_merged.parquet"
    latest = symbol_root / "usdjpy_m5_latest.parquet"
    _write_dataset(merged, ["2024-01-31T23:50:00Z", "2024-01-31T23:55:00Z"])
    _write_dataset(latest, ["2024-02-01T00:00:00Z", "2024-02-01T00:05:00Z"])

    paths = _candidate_symbol_dataset_paths(
        symbol=symbol,
        data_dir=symbol_root,
        manifest_paths={},
    )

    assert merged in paths
    assert latest in paths
