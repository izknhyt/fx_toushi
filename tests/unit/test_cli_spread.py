from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.calendar import CalendarEvent
from src.interfaces.cli import spread as spread_cli


def test_spread_inspect_uses_ntp_and_news(tmp_path: Path, monkeypatch) -> None:
    metrics_path = tmp_path / "spread.jsonl"
    audit_path = tmp_path / "spread_audit.jsonl"
    time_sync_path = tmp_path / "time_sync.jsonl"
    time_sync_path.write_text(json.dumps({"clock_drift_ms": 120}) + "\n", encoding="utf-8")
    now = datetime.now(timezone.utc)
    event = CalendarEvent(title="FOMC", timestamp=now, impact="high")

    class StubCalendarService:
        def upcoming_events(self, *, limit: int = 10) -> list[CalendarEvent]:
            return [event]

        def is_blocked(self, now: datetime) -> bool:
            return False

    monkeypatch.setattr(spread_cli, "CalendarService", StubCalendarService)

    payload = spread_cli.inspect(
        "USDJPY",
        window="30m",
        p95=1.0,
        p99=1.1,
        metrics_path=metrics_path,
        audit_path=audit_path,
        time_sync_metrics_path=time_sync_path,
    )

    assert payload["status"] == "cooldown"
    assert payload["ntp_drift_ms"] == 120
    assert payload["news_id"] == "FOMC"
    assert payload["cooldown_reason"] and "news_volatility" in payload["cooldown_reason"]
    assert payload.get("cooldown_eta")

    metrics_entry = json.loads(metrics_path.read_text(encoding="utf-8").splitlines()[-1])
    assert metrics_entry["cooldown_eta"]
