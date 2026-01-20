from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.telemetry.trader_workflow import TraderWorkflowTelemetryService


def test_trader_workflow_summary(tmp_path: Path) -> None:
    metrics_path = tmp_path / "trader_workflow.jsonl"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    events = [
        {
            "event": "ticket.proposed",
            "ts": (now - timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
            "ticket_id": "T1",
            "board_mode": "normal",
        },
        {
            "event": "ticket.ack",
            "ts": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
            "ticket_id": "T1",
            "board_mode": "normal",
        },
        {
            "event": "checklist.completed",
            "ts": now.isoformat().replace("+00:00", "Z"),
            "ticket_id": "T1",
            "board_mode": "guarded",
        },
        {
            "event": "checklist.missed",
            "ts": now.isoformat().replace("+00:00", "Z"),
            "ticket_id": "T2",
            "board_mode": "guarded",
        },
        {
            "event": "workflow.mistake",
            "ts": now.isoformat().replace("+00:00", "Z"),
            "ticket_id": "T2",
            "board_mode": "normal",
        },
    ]
    metrics_path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
    )

    service = TraderWorkflowTelemetryService(metrics_path=metrics_path)
    summary = service.summarize(window=timedelta(days=1))

    assert summary.sample_count == len(events)
    assert round(summary.avg_approval_latency_sec or 0, 2) == 60.0
    assert summary.checklist_completion_rate == 0.5
    assert summary.guarded_time_ratio == 0.4
    assert round(summary.mistake_rate or 0, 2) == 0.2
