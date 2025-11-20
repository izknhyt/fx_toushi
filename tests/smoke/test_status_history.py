from __future__ import annotations

from pathlib import Path

from src.interfaces.cli.status import status


def test_drawdown_guard_history(tmp_path: Path) -> None:
    log_path = tmp_path / "risk.kill_switch.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                '{"ts": "2025-01-01T00:00:00Z", "event": "kill_switch.engaged", "reason": "daily_drawdown"}',
                '{"ts": "2025-01-01T01:00:00Z", "event": "kill_switch.released", "reason": "ops_review"}',
            ]
        ),
        encoding="utf-8",
    )

    payload = status(history="kill-switch", kill_switch_log_path=log_path)

    assert "history" in payload
    history_section = payload["history"]["kill_switch"]
    assert history_section["status"] == "ok"
    assert len(history_section["entries"]) == 2
    assert history_section["entries"][0]["event"] == "kill_switch.engaged"
