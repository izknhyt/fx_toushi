from __future__ import annotations

import json
from pathlib import Path

from src.analytics.pnl_feedback import FeedbackVector, PnLFeedbackLoop


def test_pnl_feedback_records_adjustment(tmp_path: Path) -> None:
    metrics_path = tmp_path / "profit_loop.jsonl"
    loop = PnLFeedbackLoop(
        metrics_path=metrics_path, audit_path=tmp_path / "audit.jsonl"
    )
    entry = loop.record(
        strategy_id="m1_baseline_ma_rsi",
        pair="USDJPY",
        pulse_id="pulse-1",
        conviction=0.6,
        size_hint=1.0,
        feedback=FeedbackVector(realized_rr=1.0, target_rr=0.4),
        board_mode="normal",
        decision_latency_ms=12000,
        feedback_cycle_minutes=90,
        mode="live",
    )
    assert entry.dynamic_adjust_applied is True
    assert metrics_path.exists()
    record = json.loads(metrics_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["strategy_id"] == "m1_baseline_ma_rsi"
    assert record["mode"] == "live"


def test_pnl_feedback_respects_dynamic_disabled(tmp_path: Path) -> None:
    metrics_path = tmp_path / "profit_loop.jsonl"
    loop = PnLFeedbackLoop(
        metrics_path=metrics_path, audit_path=tmp_path / "audit.jsonl"
    )
    entry = loop.record(
        strategy_id="m1_baseline_ma_rsi",
        pair="USDJPY",
        pulse_id=None,
        conviction=0.5,
        size_hint=1.0,
        feedback=FeedbackVector(realized_rr=-1.0, target_rr=0.4),
        dynamic_enabled=False,
    )
    assert entry.dynamic_adjust_applied is False
    assert entry.size_adjust_pct == 0.0
