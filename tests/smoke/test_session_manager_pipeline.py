"""Smoke tests for the session manager to workflow hand-off."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.session import DefaultSessionManager, SessionConfig, create_session_context
from src.core.workflow import PipelineStep, PipelineWorkflow, WorkflowContext

pytestmark = pytest.mark.smoke


def test_backtest_session_executes_dummy_pipeline(tmp_path: Path) -> None:
    """Ensure a backtest session wires ModeContext and executes pipeline steps."""

    executed: list[str] = []

    def _dummy_handler(context: WorkflowContext) -> WorkflowContext:
        executed.append(context.session.session_id)
        return context

    workflow = PipelineWorkflow()
    workflow.register(PipelineStep(name="dummy", handler=_dummy_handler))

    config = SessionConfig(mode="backtest", profile_name="backtest")
    manager = DefaultSessionManager(
        config=config,
        workflow=workflow,
        session_log_dir=tmp_path / "logs",
        snapshot_root=tmp_path / "snapshots",
    )

    session_context = create_session_context(
        profile_name="backtest",
        session_id="session-smoke",
        config=config,
        factory=manager.mode_factory,
    )

    manager.start(session_context)

    assert executed == ["session-smoke"]
    assert manager.session_log_path == (tmp_path / "logs" / "session-smoke.log")
    expected_snapshot = tmp_path / "snapshots" / "backtest" / "session-smoke.json"
    assert manager.request_snapshot() == str(expected_snapshot)
    assert manager.last_plan == ("dummy",)
    assert manager.last_workflow_context is not None
    assert manager.last_workflow_context.step_sequence == ("dummy",)
    assert manager.last_workflow_context.planned_steps == ("dummy",)

    manager.stop()
    assert manager.request_snapshot() is None
