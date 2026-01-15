"""Tests for the ``tradectl resync`` helper."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import importlib
import json
from typing import Any

resync_module = importlib.import_module("src.interfaces.cli.resync")


class _SessionStub:
    def __init__(
        self, *, result: Mapping[str, Any] | None = None, error: Exception | None = None
    ) -> None:
        self._result = result
        self._error = error
        self.calls: list[Mapping[str, Any]] = []

    def catch_up(
        self,
        *,
        since: str | None = None,
        symbols: Sequence[str] | None = None,
        force: bool = False,
        failover_report: bool = False,
        dry_run: bool = False,
        attachments: Sequence[str] | None = None,
    ) -> Mapping[str, Any] | None:
        call = {
            "since": since,
            "symbols": list(symbols or ()),
            "force": force,
            "failover_report": failover_report,
            "dry_run": dry_run,
            "attachments": list(attachments or ()),
        }
        self.calls.append(call)
        if self._error:
            raise self._error
        return self._result


def test_resync_returns_unavailable_when_session_is_missing() -> None:
    payload = resync_module.resync(session=None)
    assert payload["status"] == "unavailable"
    assert "error" in payload


def test_resync_returns_unimplemented_when_session_raises() -> None:
    session = _SessionStub(error=NotImplementedError("catch_up not wired"))
    payload = resync_module.resync(session=session)
    assert payload["status"] == "unimplemented"
    assert "catch_up not wired" in payload["error"]


def test_resync_success_path_serialises_summary_and_arguments() -> None:
    session = _SessionStub(result={"catch_up_elapsed_sec": 45, "windows": 3})
    payload = resync_module.resync(
        session=session,
        since="2025-03-18T10:00:00Z",
        symbols=["USDJPY", "EURUSD"],
        force=True,
        failover_report=True,
        dry_run=False,
        attachments=["reports/gaps/USDJPY.md"],
        verbose=True,
        json_output=True,
    )

    assert payload["status"] == "ok"
    assert payload["summary"] == {"catch_up_elapsed_sec": 45, "windows": 3}
    assert session.calls[-1]["since"] == "2025-03-18T10:00:00Z"
    assert session.calls[-1]["symbols"] == ["USDJPY", "EURUSD"]
    assert session.calls[-1]["force"] is True
    assert session.calls[-1]["failover_report"] is True


def test_apply_catch_up_health_uses_degraded_for_30_min_lag(
    tmp_path, monkeypatch
) -> None:
    health_state_path = tmp_path / "health_state.json"
    monkeypatch.setattr(resync_module, "DEFAULT_HEALTH_STATE_PATH", health_state_path)
    monkeypatch.setattr(
        resync_module, "DEFAULT_HEALTH_ACTION_AUDIT", tmp_path / "health_action.jsonl"
    )
    monkeypatch.setattr(
        resync_module, "DEFAULT_HEALTH_SUGGEST_LOG", tmp_path / "health_suggested.jsonl"
    )

    summary = {"catch_up_lag_minutes": 30}
    result = resync_module._apply_catch_up_health(
        summary, log_path=tmp_path / "resync_events.jsonl"
    )

    assert result is not None
    assert result["action"] == "guarded"
    payload = json.loads(health_state_path.read_text(encoding="utf-8"))
    assert payload["status"] == "degraded"
