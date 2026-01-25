from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.core.health_store import HealthStateStore


def test_health_store_records_transition_and_counters(tmp_path: Path) -> None:
    store = HealthStateStore(
        state_path=tmp_path / "data" / "health" / "state.json",
        history_path=tmp_path / "data" / "health" / "history.jsonl",
        ledger_path=tmp_path / "data" / "health" / "degraded_ack_ledger.jsonl",
    )
    event = {
        "ts": "2026-01-20T00:00:00Z",
        "from_state": "ok",
        "to_state": "degraded",
        "reason": "data_latency",
        "runbook_ref": "RUN-DATA-05#enter_guarded",
    }
    summary = store.record_transition(event)
    assert summary.current_state == "degraded"
    assert summary.rolling_30d_degraded_count == 1
    assert store.list_history()

    ack_seq = store.record_degraded_ack({"ack_id": "ack-1", "actor": "ops"})
    assert ack_seq >= 0


def test_health_store_refresh_counts(tmp_path: Path) -> None:
    store = HealthStateStore(
        state_path=tmp_path / "data" / "health" / "state.json",
        history_path=tmp_path / "data" / "health" / "history.jsonl",
        ledger_path=tmp_path / "data" / "health" / "degraded_ack_ledger.jsonl",
    )
    history_path = tmp_path / "data" / "health" / "history.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        "\n".join(
            [
                '{"ts":"2026-01-01T00:00:00Z","from":"ok","to":"degraded","reason":"x"}',
                '{"ts":"2026-01-05T00:00:00Z","from":"degraded","to":"ok","reason":"clear"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    now = datetime(2026, 1, 6, tzinfo=timezone.utc)
    summary = store.refresh_counters(now=now)
    assert summary.last_ok_ts == "2026-01-05T00:00:00Z"
    assert summary.business_days_since_last_ok >= 0
    assert summary.rolling_30d_degraded_count == 1

    recent = store.list_history(since=timedelta(days=3), now=now)
    assert recent
