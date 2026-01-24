from __future__ import annotations

from pathlib import Path

from src.interfaces.gui.tauri_app.telemetry import GuiTelemetryRecorder


def test_gui_telemetry_records_event(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics" / "gui_board.jsonl"
    recorder = GuiTelemetryRecorder(metrics_path=metrics_path, session_id="sess-1")
    entry = recorder.record(
        {
            "user_role": "ops",
            "command": "ticket.approve",
            "result": "ok",
            "latency_ms": 1200,
            "shadow_roundtrip_ms": 5000,
        }
    )
    assert metrics_path.exists()
    assert entry["session_id"] == "sess-1"
    assert entry["warn_latency"] is True
    assert entry["warn_shadow_roundtrip"] is True
