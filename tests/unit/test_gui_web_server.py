import time
from pathlib import Path

from src.interfaces.gui.web_server import (
    GuiOpsRuntimeConfig,
    GuiOpsRuntimeController,
    _read_last_line,
    _read_latest_price_from_csv,
    resolve_sync_source_dir,
)


def test_read_last_line(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    assert _read_last_line(path) == "3,4"


def test_read_latest_price_from_csv(tmp_path: Path) -> None:
    path = tmp_path / "price.csv"
    path.write_text("ts,open,high,low,close\n2024-01-01,1,2,0.5,1.5\n", encoding="utf-8")
    row = _read_latest_price_from_csv(path, price_column="close", ts_column="ts")
    assert row is not None
    assert row["close"] == "1.5"
    assert row["ts"] == "2024-01-01"


def test_resolve_sync_source_dir_prefers_m5_clean(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/research/curated/usdjpy_m5_clean").mkdir(parents=True)
    (tmp_path / "data/research/curated/usdjpy").mkdir(parents=True)
    resolved = resolve_sync_source_dir("USDJPY")
    assert resolved == Path("data/research/curated/usdjpy_m5_clean")


def test_gui_ops_runtime_controller_start_stop(monkeypatch, tmp_path: Path) -> None:
    class _SyncResult:
        def to_dict(self) -> dict[str, str]:
            return {"phase": "sync"}

    class _LoopResult:
        def to_dict(self) -> dict[str, object]:
            return {"signal_preview": {"signals": 0}}

    monkeypatch.setattr(
        "src.interfaces.cli.gui_sync.run_gui_data_sync",
        lambda **_: _SyncResult(),
    )
    monkeypatch.setattr(
        "tools.gui_ops_loop.run_gui_ops_once",
        lambda **_: _LoopResult(),
    )

    config = GuiOpsRuntimeConfig(
        symbol="USDJPY",
        source_dir=tmp_path / "curated/usdjpy_m5_clean",
        manifest=tmp_path / "reports/data_manifest.json",
        validation_dir=tmp_path / "reports/validation_log",
        latest_days=30,
        gap_minutes=5,
        chunk_hours=6,
        gap_exclude_weekend=True,
        run_fetch_plan=False,
        provider="twelvedata",
        symbols=["USDJPY"],
        timeframe="5m",
        lookback_hours=6,
        raw_dir=tmp_path / "data/raw",
        curated_dir=tmp_path / "data/research/curated",
        metrics_path=tmp_path / "metrics/data_ingestion_sla.jsonl",
        price_csv_dir=tmp_path / "reports/price",
        bootstrap_rows=100,
        profile_path=tmp_path / "config/profiles/paper.yaml",
        data_dir=tmp_path / "data/research/curated",
        feature_config=tmp_path / "config/feature_pipeline.yaml",
        strategy_manifest=tmp_path / "config/strategy_manifest.yaml",
        signal_log_path=tmp_path / "logs/events/signal.gui.jsonl",
        backfill_days=30,
        target_r_multiple=0.8,
        ttl_bars=4,
        trail_atr_mult=1.2,
        spread_pips=0.005,
        slippage_pips=0.0015,
        slippage_std=0.001,
        interval_sec=1,
        signals_csv_append=True,
        signals_csv_monthly=True,
    )
    controller = GuiOpsRuntimeController(config)
    started = controller.start()
    assert started["accepted"] is True

    for _ in range(20):
        snapshot = controller.snapshot()
        if snapshot["loop_iterations"] >= 1:
            break
        time.sleep(0.05)
    assert snapshot["running"] is True
    assert snapshot["last_sync"] == {"phase": "sync"}

    stopped = controller.stop()
    assert stopped["accepted"] is True
    for _ in range(30):
        snapshot = controller.snapshot()
        if snapshot["running"] is False:
            break
        time.sleep(0.05)
    assert snapshot["running"] is False
