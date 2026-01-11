from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.core.health import HealthMonitor
from src.core.time_sync import TimeSyncGuard


def _write_entry(path: Path, *, drift_ms: float) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "clock_drift_ms": drift_ms,
        "status": "ok",
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_time_sync_guard_suggests_guarded(tmp_path: Path) -> None:
    metrics_path = tmp_path / "time_sync.jsonl"
    _write_entry(metrics_path, drift_ms=800)
    monitor = HealthMonitor()
    guard = TimeSyncGuard(warn_threshold_ms=500)

    result = guard.evaluate(
        metrics_path=metrics_path,
        monitor=monitor,
        health_state_path=tmp_path / "health_state.json",
        suggest_log_path=tmp_path / "health_suggest.jsonl",
        audit_path=tmp_path / "health_audit.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        persist_health_state=True,
        log_events=True,
    )

    assert result.status == "warn"
    assert result.action == "guarded"
    assert (tmp_path / "health_state.json").exists()
    assert (tmp_path / "health_suggest.jsonl").exists()


def test_time_sync_guard_suggests_resume(tmp_path: Path) -> None:
    metrics_path = tmp_path / "time_sync.jsonl"
    entries = []
    now = datetime.now(timezone.utc)
    for offset in (0, 5, 10):
        entries.append(
            {
                "ts": (now - timedelta(minutes=offset)).isoformat().replace("+00:00", "Z"),
                "clock_drift_ms": 50,
                "status": "ok",
            }
        )
    metrics_path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8")
    monitor = HealthMonitor()
    guard = TimeSyncGuard(resume_min_samples=3, resume_window_minutes=30)

    result = guard.evaluate(
        metrics_path=metrics_path,
        monitor=monitor,
        health_state_path=tmp_path / "health_state.json",
        suggest_log_path=tmp_path / "health_suggest.jsonl",
        audit_path=tmp_path / "health_audit.jsonl",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        persist_health_state=True,
        log_events=True,
    )

    assert result.status == "recovered"
    assert result.action == "resume"
