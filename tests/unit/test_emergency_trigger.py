from __future__ import annotations

from pathlib import Path

import pytest

from src.infra.alert import AlertDispatcher
from src.ops.emergency import trigger


def test_emergency_trigger_warn(tmp_path: Path) -> None:
    log_path = tmp_path / "emergency.jsonl"
    worklog_path = tmp_path / "ops_worklog.jsonl"
    alert_log = tmp_path / "alerts.jsonl"
    dispatcher = AlertDispatcher(log_path=alert_log)

    result = trigger(
        scenario="test_scenario",
        runbook=None,
        simulate=False,
        severity="warn",
        log_path=log_path,
        ops_worklog_path=worklog_path,
        dispatcher=dispatcher,
    )

    assert result.status == "triggered"
    assert log_path.exists()
    assert worklog_path.exists()
    assert alert_log.exists()


def test_emergency_trigger_requires_runbook_for_critical(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        trigger(scenario="critical", severity="critical", log_path=tmp_path / "log.jsonl")
