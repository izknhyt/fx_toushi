from __future__ import annotations

import asyncio
from pathlib import Path

from src.core.health_jobs import HealthEscalationJob
from src.core.health_store import HealthStateStore


def test_health_escalation_job_emits_event(tmp_path: Path) -> None:
    state_path = tmp_path / "data" / "health" / "state.json"
    history_path = tmp_path / "data" / "health" / "history.jsonl"
    store = HealthStateStore(state_path=state_path, history_path=history_path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        "\n".join(
            [
                '{"ts":"2026-01-01T00:00:00Z","from":"ok","to":"degraded","reason":"x"}',
                '{"ts":"2026-01-02T00:00:00Z","from":"degraded","to":"degraded","reason":"y"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    job = HealthEscalationJob(
        store=store,
        event_log=tmp_path / "logs" / "events" / "health_escalate.jsonl",
        business_days_threshold=0,
        rolling_count_threshold=1,
    )
    result = asyncio.run(job.run())
    assert result.escalated is True
    assert result.event_payload is not None
    assert (tmp_path / "logs" / "events" / "health_escalate.jsonl").exists()

def test_health_escalation_job_no_escalation(tmp_path: Path) -> None:
    store = HealthStateStore(
        state_path=tmp_path / "data" / "health" / "state.json",
        history_path=tmp_path / "data" / "health" / "history.jsonl",
    )
    job = HealthEscalationJob(
        store=store,
        event_log=tmp_path / "logs" / "events" / "health_escalate.jsonl",
        business_days_threshold=10,
        rolling_count_threshold=5,
    )
    result = asyncio.run(job.run())
    assert result.escalated is False
