from pathlib import Path

import pandas as pd

import os

from tools.gui_ops_loop import (
    _detect_breakouts,
    _ensure_signal_log,
    _load_dotenv,
    append_price_csv,
)


def test_append_price_csv_dedup(tmp_path: Path) -> None:
    curated = tmp_path / "curated.parquet"
    df = pd.DataFrame(
        {
            "timestamp": ["2024-01-01T00:00:00Z", "2024-01-01T00:05:00Z"],
            "open": [1.0, 1.1],
            "high": [1.2, 1.3],
            "low": [0.9, 1.0],
            "close": [1.05, 1.15],
        }
    )
    df.to_parquet(curated, index=False)

    out_dir = tmp_path / "price"
    first = append_price_csv(
        curated_path=curated,
        output_dir=out_dir,
        symbol="USDJPY",
        bootstrap_rows=1000,
    )
    assert first["appended"] == 2

    second = append_price_csv(
        curated_path=curated,
        output_dir=out_dir,
        symbol="USDJPY",
        bootstrap_rows=1000,
    )
    assert second["appended"] == 0

    csv_path = out_dir / "usdjpy_m5.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_load_dotenv_sets_env(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("FOO=bar\n# comment\nEMPTY=\nQUOTED='baz'\n", encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("EMPTY", raising=False)
    monkeypatch.delenv("QUOTED", raising=False)

    _load_dotenv(env_path)

    assert os.getenv("FOO") == "bar"
    assert os.getenv("EMPTY") == ""
    assert os.getenv("QUOTED") == "baz"


def test_ensure_signal_log_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "events" / "signal.gui.jsonl"
    _ensure_signal_log(path)
    assert path.exists()


def test_detect_breakouts_emits_records() -> None:
    index = pd.to_datetime(
        ["2026-01-28T06:00:00Z", "2026-01-28T06:05:00Z"], utc=True
    )
    df = pd.DataFrame(
        {
            "donchian_upper20_1h": [150.0, 150.0],
            "donchian_lower20_1h": [140.0, 140.0],
            "donchian_mid20_1h": [145.0, 145.0],
            "close_5m": [151.0, 139.0],
            "atr_14_1h": [5.0, 5.0],
        },
        index=index,
    )
    records = _detect_breakouts(
        df,
        "USDJPY",
        strategy_id="m1_baseline_donchian",
        mode="bidirectional",
        entry_minutes=60,
        target_r_multiple=1.1,
        ttl_bars=6,
        trail_atr_mult=0.7,
        spread_pips=0.001,
        slippage_pips=0.0015,
        slippage_std=0.001,
    )
    assert len(records) == 2
    by_breakout = {record["breakout"]: record for record in records}
    assert by_breakout["upper"]["direction"] == "long"
    assert by_breakout["lower"]["direction"] == "short"


def test_detect_breakouts_mode_overrides() -> None:
    index = pd.to_datetime(
        ["2026-01-28T06:00:00Z", "2026-01-28T06:05:00Z"], utc=True
    )
    df = pd.DataFrame(
        {
            "donchian_upper20_1h": [150.0, 150.0],
            "donchian_lower20_1h": [140.0, 140.0],
            "donchian_mid20_1h": [145.0, 145.0],
            "close_5m": [151.0, 139.0],
            "atr_14_1h": [5.0, 5.0],
        },
        index=index,
    )
    long_only = _detect_breakouts(
        df,
        "USDJPY",
        strategy_id="m1_baseline_donchian_long_only",
        mode="long_only",
        entry_minutes=60,
        target_r_multiple=1.1,
        ttl_bars=6,
        trail_atr_mult=0.7,
        spread_pips=0.001,
        slippage_pips=0.0015,
        slippage_std=0.001,
    )
    assert len(long_only) == 2
    assert {record["direction"] for record in long_only} == {"long"}

    upper_only = _detect_breakouts(
        df,
        "USDJPY",
        strategy_id="m1_baseline_donchian_upper_only",
        mode="upper_only",
        entry_minutes=60,
        target_r_multiple=1.1,
        ttl_bars=6,
        trail_atr_mult=0.7,
        spread_pips=0.001,
        slippage_pips=0.0015,
        slippage_std=0.001,
    )
    assert len(upper_only) == 1
    assert upper_only[0]["breakout"] == "upper"
