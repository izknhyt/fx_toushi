from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.risk.liquidity_monitor import (
    LiquidityMonitorService,
    LiquiditySample,
    LiquidityThresholds,
)


def _sample(
    *,
    source: str,
    symbol: str = "USDJPY",
    bid: float,
    ask: float,
    latency_ms: float = 200.0,
) -> LiquiditySample:
    return LiquiditySample(
        source=source,
        symbol=symbol,
        ts=datetime.now(timezone.utc),
        bid=bid,
        ask=ask,
        spread=ask - bid,
        update_latency_ms=latency_ms,
    )


def test_liquidity_monitor_marks_guarded_on_divergence(tmp_path: Path) -> None:
    service = LiquidityMonitorService(
        metrics_path=tmp_path / "metrics.jsonl",
        snapshot_path=tmp_path / "snapshot.json",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        gate_state_path=tmp_path / "gate_state.json",
        validation_dir=tmp_path,
    )
    thresholds = LiquidityThresholds(divergence_warn_pips=1.0, divergence_alert_pips=5.0)
    snapshot = service.update(
        [
            _sample(source="a", bid=150.00, ask=150.01),
            _sample(source="b", bid=150.03, ask=150.04),
        ],
        thresholds=thresholds,
    )
    assert snapshot.state == "guarded"
    assert snapshot.alerts
    assert (tmp_path / "ops_worklog.jsonl").exists()
    assert list(tmp_path.glob("liquidity_alert_*.md"))


def test_liquidity_monitor_marks_halted_on_latency(tmp_path: Path) -> None:
    service = LiquidityMonitorService(
        metrics_path=tmp_path / "metrics.jsonl",
        snapshot_path=tmp_path / "snapshot.json",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        gate_state_path=tmp_path / "gate_state.json",
        validation_dir=tmp_path,
    )
    thresholds = LiquidityThresholds(latency_warn_ms=100.0, latency_alert_ms=200.0)
    snapshot = service.update(
        [_sample(source="a", bid=150.00, ask=150.01, latency_ms=250.0)],
        thresholds=thresholds,
    )
    assert snapshot.state == "halted"
    assert snapshot.alerts
