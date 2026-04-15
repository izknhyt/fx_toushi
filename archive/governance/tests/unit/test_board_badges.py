"""Board CLI badge rendering."""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch
from src.interfaces.cli.board import board


def test_board_includes_profit_and_execution_badges(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    manifest = tmp_path / "reports/data_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '{"strategies":{"m1_baseline_ma_rsi":{"dataset_path":"data/research/curated/usdjpy/usdjpy_m5_20210101_20241231.parquet","dataset_sha256":"sha256:abc123"}}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("RISK_DISCLOSURE_STATE_PATH", str(tmp_path / "risk_state.json"))

    payload = board(
        guarded=True,
        profit_readiness_status="guarded",
        latency_data_status="degraded",
        slippage_data_status="halt_recommended",
        manifest_path=manifest,
    )

    badges = payload.get("badges", {})
    assert badges.get("profit_readiness") == "guarded"
    execution = badges.get("execution_stats", {})
    assert execution.get("latency_data_status") == "degraded"
    assert execution.get("slippage_data_status") == "halt_recommended"
