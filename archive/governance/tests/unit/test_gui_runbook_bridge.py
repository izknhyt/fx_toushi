from __future__ import annotations

import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from src.interfaces.gui.tauri_app.runbook_bridge import RunbookBridge


def test_runbook_bridge_fetch_and_ack(tmp_path: Path) -> None:
    runbook_dir = tmp_path / "runbooks"
    runbook_dir.mkdir(parents=True, exist_ok=True)
    runbook_path = runbook_dir / "RUN-GUI-BOARD-01.md"
    content = "# Test Runbook\n"
    runbook_path.write_text(content, encoding="utf-8")
    fixed_time = datetime(2026, 1, 24, 5, 0, tzinfo=timezone.utc).timestamp()
    os.utime(runbook_path, (fixed_time, fixed_time))

    ack_path = tmp_path / "acks.jsonl"
    bridge = RunbookBridge(runbook_dir=runbook_dir, ack_log_path=ack_path)
    payload = bridge.fetch("RUN-GUI-BOARD-01")
    assert "Test Runbook" in payload.content
    assert payload.updated_at == "2026-01-24T05:00:00Z"
    assert payload.content_hash == sha256(content.encode("utf-8")).hexdigest()

    ack = bridge.acknowledge(runbook_id="RUN-GUI-BOARD-01", user="ops")
    assert ack_path.exists()
    assert ack["user"] == "ops"
    assert ack["content_hash"] == payload.content_hash
