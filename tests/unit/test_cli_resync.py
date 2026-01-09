"""Tests for the ``tradectl resync`` helper."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.interfaces.cli.resync import resync


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
    payload = resync(session=None)
    assert payload["status"] == "unavailable"
    assert "error" in payload


def test_resync_returns_unimplemented_when_session_raises() -> None:
    session = _SessionStub(error=NotImplementedError("catch_up not wired"))
    payload = resync(session=session)
    assert payload["status"] == "unimplemented"
    assert "catch_up not wired" in payload["error"]


def test_resync_success_path_serialises_summary_and_arguments() -> None:
    session = _SessionStub(result={"catch_up_elapsed_sec": 45, "windows": 3})
    payload = resync(
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
