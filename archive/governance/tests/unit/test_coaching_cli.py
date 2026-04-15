from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src.interfaces.cli.ops import coaching_insight_create, coaching_review, coaching_summary


def _write_thresholds(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "version: 1",
                "thresholds:",
                "  avg_approval_latency_sec: 45",
                "  checklist_completion_rate_min: 0.9",
                "  guarded_time_ratio_max: 0.5",
                "  mistake_rate_max: 0.2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_coaching_cli_flow(tmp_path: Path) -> None:
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
    ]
    metrics_path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
    )

    export_summary = tmp_path / "summary.md"
    summary = coaching_summary(window="7d", export_md=export_summary, metrics_path=metrics_path)
    assert summary["status"] == "ok"
    assert export_summary.exists()

    threshold_path = tmp_path / "thresholds.yaml"
    _write_thresholds(threshold_path)
    insights_log = tmp_path / "coaching_insights.jsonl"
    export_insights = tmp_path / "insights.md"
    insights = coaching_insight_create(
        window="7d",
        threshold_config=threshold_path,
        export_md=export_insights,
        metrics_path=metrics_path,
        insights_log=insights_log,
    )
    assert insights["status"] == "ok"
    assert export_insights.exists()
    assert insights_log.exists()

    week = date.today().strftime("%G-W%V")
    review = coaching_review(week=week, export_md=tmp_path / "review.md", insights_log=insights_log)
    assert review["status"] == "ok"
