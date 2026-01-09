from __future__ import annotations

from pytest import MonkeyPatch
from src.interfaces.gui.tauri_app.serializer import kill_switch_set


def test_kill_switch_set_delegates_to_cli(monkeypatch: MonkeyPatch) -> None:
    called = {}

    def fake_set_state(
        *, state: str, reason: str | None, actor: str | None, runbook: str | None
    ) -> None:
        called["state"] = state
        called["reason"] = reason
        called["actor"] = actor
        called["runbook"] = runbook

    monkeypatch.setattr(
        "src.interfaces.gui.tauri_app.serializer.cli_kill_switch_set", fake_set_state
    )

    resp = kill_switch_set(
        state="soft_stop", reason="spread_block", actor="ops", runbook="RUN-RISK-01"
    )
    assert resp["status"] == "accepted"
    assert called["state"] == "soft_stop"
