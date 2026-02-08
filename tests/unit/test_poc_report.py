from __future__ import annotations

import json
from pathlib import Path

from src.backtest.poc_report import build_poc_report


def test_build_poc_report_summary(tmp_path: Path) -> None:
    poc_path = tmp_path / "poc.json"
    payload = {
        "metrics": {"pf_all": 1.2, "win_rate": 0.5},
        "trades": [
            {
                "opened_at": "2024-01-02T00:00:00Z",
                "closed_at": "2024-01-02T00:05:00Z",
                "symbol": "USDJPY",
                "direction": "long",
                "entry": 100.0,
                "exit": 101.0,
                "stop": 99.0,
                "target": 102.0,
                "r_multiple": 1.0,
                "pnl": 100.0,
                "breakout": "upper",
                "quality_score": 1.4,
                "trend_value": 0.4,
                "atr_value": 0.12,
                "spread_used": 0.005,
                "slippage_used": 0.001,
                "breakout_width": 0.03,
            },
            {
                "opened_at": "2024-01-03T10:00:00Z",
                "closed_at": "2024-01-03T10:05:00Z",
                "symbol": "USDJPY",
                "direction": "short",
                "entry": 101.0,
                "exit": 102.0,
                "stop": 103.0,
                "target": 99.0,
                "r_multiple": -0.5,
                "pnl": -50.0,
                "breakout": "lower",
                "quality_score": 0.8,
                "trend_value": -0.4,
                "atr_value": 0.04,
                "spread_used": 0.005,
                "slippage_used": 0.001,
                "breakout_width": 0.004,
            },
        ],
    }
    poc_path.write_text(json.dumps(payload), encoding="utf-8")

    report = build_poc_report(poc_path)

    summary = report["summary"]
    assert summary["count"] == 2
    assert summary["win_rate"] == 0.5
    assert summary["avg_r"] == 0.25
    assert "by_direction" in report
    assert "long" in report["by_direction"]
    assert "short" in report["by_direction"]
    assert report["by_quality"]["1_2"]["count"] == 1
    assert report["by_quality"]["lt_1"]["count"] == 1
    assert report["by_trend_band"]["ge_0_3"]["count"] == 1
    assert report["by_trend_band"]["lt_-0_3"]["count"] == 1
    assert "by_atr_band" in report
    assert "by_cost_ratio" in report
    assert "by_weekday" in report
    assert "by_loss_streak" in report
    assert report["economics"]["break_even_win_rate"] == 0.3333
    assert report["acceptance_gate"]["status"] == "fail"
    assert report["acceptance_gate"]["checks"]["trade_count_ge_300"] is False
    assert "next_actions" in report
