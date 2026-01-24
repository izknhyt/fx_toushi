from __future__ import annotations

from pathlib import Path

import pytest
from src.brokers.fill_drift import FillDriftDetector
from src.brokers.fill_replay import FillReplayError, FillReplayService
from src.brokers.fill_shadow import FillShadowRecorder, FillShadowStore
from src.reports.broker_shadow import render_shadow_report


def test_broker_shadow_replay_and_report(tmp_path: Path) -> None:
    store = FillShadowStore(
        event_log_path=tmp_path / "shadow_events.jsonl",
        session_log_path=tmp_path / "shadow_sessions.jsonl",
    )
    recorder = FillShadowRecorder(store=store)
    recorder.record(
        ticket_id="ticket-1",
        order_id="order-1",
        status="filled",
        adapter="sandbox",
        profile="paper",
        payload={
            "symbol": "EURUSD",
            "expected_price": 1.1000,
            "fill_price": 1.1002,
        },
    )

    detector = FillDriftDetector(
        metrics_path=tmp_path / "broker_shadow.jsonl",
        event_log_path=tmp_path / "shadow_events.jsonl",
    )
    service = FillReplayService(detector=detector)
    report = service.replay(store.list_records(), strict=False)
    assert report.total_records == 1
    assert report.drift_alerts

    report_path = render_shadow_report(report, outdir=tmp_path / "reports")
    assert report_path.exists()

    with pytest.raises(FillReplayError):
        service.replay(store.list_records(), strict=True)
