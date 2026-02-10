from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import json

import os

from tools.gui_ops_loop import (
    _backfill_signals,
    _detect_breakouts,
    _engine_signal_payload,
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


def test_append_price_csv_uses_ts_when_timestamp_is_empty(tmp_path: Path) -> None:
    curated = tmp_path / "curated.parquet"
    df = pd.DataFrame(
        {
            "timestamp": [None, None],
            "ts": ["2026-02-09T09:20:00Z", "2026-02-09T09:25:00Z"],
            "open": [150.1, 150.2],
            "high": [150.2, 150.3],
            "low": [150.0, 150.1],
            "close": [150.15, 150.25],
        }
    )
    df.to_parquet(curated, index=False)

    out_dir = tmp_path / "price"
    payload = append_price_csv(
        curated_path=curated,
        output_dir=out_dir,
        symbol="USDJPY",
        bootstrap_rows=1000,
    )
    assert payload["appended"] == 2
    assert payload["last_ts"] == "2026-02-09T09:25:00Z"
    csv_path = out_dir / "usdjpy_m5.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "timestamp,open,high,low,close,volume"
    assert len(lines[1].split(",")) == 6


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


def test_load_dotenv_overrides_empty_env_var(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("TWELVEDATA_API_KEY=abc123\n", encoding="utf-8")
    monkeypatch.setenv("TWELVEDATA_API_KEY", "")

    _load_dotenv(env_path)

    assert os.getenv("TWELVEDATA_API_KEY") == "abc123"


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


def test_backfill_signals_includes_non_donchian_strategies(
    tmp_path: Path, monkeypatch
) -> None:
    now = pd.Timestamp.now(tz="UTC").floor("5min")
    timestamps = pd.date_range(end=now, periods=240, freq="5min", tz="UTC")
    prices = pd.Series(range(len(timestamps)), dtype="float64") * 0.01 + 150.0
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": prices,
            "high": prices + 0.03,
            "low": prices - 0.03,
            "close": prices + 0.01,
            "volume": 1.0,
        }
    )
    data_dir = tmp_path / "curated"
    symbol_dir = data_dir / "usdjpy"
    symbol_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(symbol_dir / "usdjpy_m5_latest.parquet", index=False)

    signal_log = tmp_path / "logs/events/signal.gui.jsonl"
    signal_log.parent.mkdir(parents=True, exist_ok=True)
    signal_log.touch()

    def _fake_run_all(self, **kwargs):  # noqa: ANN001
        _ = self
        _ = kwargs
        return [
            SimpleNamespace(
                strategy_id="m1_us_session_trend_pullback",
                direction="long",
                confidence=0.7,
                rationale="mock_signal",
                score=0.9,
                quality_score=1.1,
            )
        ]

    monkeypatch.setattr("src.strategies.registry.StrategyEngine.run_all", _fake_run_all)

    payload = _backfill_signals(
        symbols=["USDJPY"],
        data_dir=data_dir,
        feature_config=Path("config/feature_pipeline.yaml"),
        strategy_manifest=Path("config/strategy_manifest.hybrid_us_experiment.yaml"),
        data_manifest=tmp_path / "missing_manifest.json",
        signal_log_path=signal_log,
        backfill_days=30,
        target_r_multiple=0.8,
        ttl_bars=4,
        trail_atr_mult=1.2,
        spread_pips=0.005,
        slippage_pips=0.0015,
        slippage_std=0.001,
    )

    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["appended"] > 0
    lines = [line for line in signal_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    assert any("m1_us_session_trend_pullback" in line for line in lines)
    first = json.loads(lines[0])
    assert first["entry"] is not None
    assert first["stop"] is not None
    assert first["target"] is not None
    assert first["expire_at"] is not None


def test_backfill_signals_uses_latest_dataset_when_manifest_path_is_stale(
    tmp_path: Path, monkeypatch
) -> None:
    now = pd.Timestamp.now(tz="UTC").floor("5min")
    fresh_timestamps = pd.date_range(end=now, periods=240, freq="5min", tz="UTC")
    stale_timestamps = pd.date_range(
        start=pd.Timestamp("2025-10-01T00:00:00Z"), periods=240, freq="5min", tz="UTC"
    )
    fresh_prices = pd.Series(range(len(fresh_timestamps)), dtype="float64") * 0.01 + 156.0
    stale_prices = pd.Series(range(len(stale_timestamps)), dtype="float64") * 0.01 + 1.55

    data_dir = tmp_path / "curated"
    symbol_dir = data_dir / "usdjpy"
    symbol_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "timestamp": fresh_timestamps,
            "open": fresh_prices,
            "high": fresh_prices + 0.03,
            "low": fresh_prices - 0.03,
            "close": fresh_prices + 0.01,
            "volume": 1.0,
        }
    ).to_parquet(symbol_dir / "usdjpy_m5_latest.parquet", index=False)

    stale_path = symbol_dir / "usdjpy_m5_20251001_20251002_merged.parquet"
    pd.DataFrame(
        {
            "timestamp": stale_timestamps,
            "open": stale_prices,
            "high": stale_prices + 0.03,
            "low": stale_prices - 0.03,
            "close": stale_prices + 0.01,
            "volume": 1.0,
        }
    ).to_parquet(stale_path, index=False)

    data_manifest = tmp_path / "data_manifest.json"
    data_manifest.write_text(
        json.dumps(
            {
                "strategies": {
                    "m1": {
                        "watchlist_datasets": {
                            "USDJPY": {"path": str(stale_path)},
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    signal_log = tmp_path / "logs/events/signal.gui.jsonl"
    signal_log.parent.mkdir(parents=True, exist_ok=True)
    signal_log.touch()

    def _fake_run_all(self, **kwargs):  # noqa: ANN001
        _ = self
        _ = kwargs
        return [
            SimpleNamespace(
                strategy_id="m1_us_session_trend_pullback",
                direction="long",
                confidence=0.7,
                rationale="mock_signal",
                score=0.9,
                quality_score=1.1,
            )
        ]

    monkeypatch.setattr("src.strategies.registry.StrategyEngine.run_all", _fake_run_all)

    payload = _backfill_signals(
        symbols=["USDJPY"],
        data_dir=data_dir,
        feature_config=Path("config/feature_pipeline.yaml"),
        strategy_manifest=Path("config/strategy_manifest.hybrid_us_experiment.yaml"),
        data_manifest=data_manifest,
        signal_log_path=signal_log,
        backfill_days=2,
        target_r_multiple=0.8,
        ttl_bars=4,
        trail_atr_mult=1.2,
        spread_pips=0.005,
        slippage_pips=0.0015,
        slippage_std=0.001,
    )
    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["appended"] > 0


def test_engine_signal_payload_sets_order_fields() -> None:
    ts = pd.Timestamp("2026-02-09T10:00:00Z", tz="UTC").to_pydatetime()
    row = pd.Series({"close_5m": 156.5, "atr_14_1h": 0.12})
    signal = SimpleNamespace(
        strategy_id="m1_us_session_trend_pullback",
        direction="short",
        confidence=0.8,
        rationale="resume",
        score=1.1,
        quality_score=1.0,
    )
    payload = _engine_signal_payload(
        signal=signal,
        ts=ts,
        symbol="USDJPY",
        row=row,
        strategy_parameters={
            "entry": {"timeframe": "5m"},
            "sizing": {"atr_sl_mult": 1.0, "tp_r_multiple": 1.8, "ttl_bars": 8},
            "execution": {"spread": 0.005, "slippage": 0.0015, "slippage_std": 0.001},
        },
        default_target_r_multiple=0.8,
        default_ttl_bars=4,
        default_trail_atr_mult=1.2,
        default_spread_pips=0.005,
        default_slippage_pips=0.0015,
        default_slippage_std=0.001,
    )
    assert payload["entry"] is not None
    assert payload["stop"] is not None
    assert payload["target"] is not None
    assert payload["expire_at"] is not None
    assert payload["ttl_bars"] == 8
    assert payload["entry"] > 100.0


def test_engine_signal_payload_skips_invalid_price_scale() -> None:
    ts = pd.Timestamp("2026-02-09T10:00:00Z", tz="UTC").to_pydatetime()
    row = pd.Series({"close_5m": 78800.0, "atr_14_1h": 1.5})
    signal = SimpleNamespace(
        strategy_id="m1_us_session_trend_pullback",
        direction="long",
        confidence=0.8,
        rationale="resume",
        score=1.1,
        quality_score=1.0,
    )
    payload = _engine_signal_payload(
        signal=signal,
        ts=ts,
        symbol="USDJPY",
        row=row,
        strategy_parameters={},
        default_target_r_multiple=0.8,
        default_ttl_bars=4,
        default_trail_atr_mult=1.2,
        default_spread_pips=0.005,
        default_slippage_pips=0.0015,
        default_slippage_std=0.001,
    )
    assert payload["entry"] is not None
    assert payload["stop"] is not None
    assert payload["target"] is not None
    assert payload["entry"] < 300.0
