"""Governance CLI helpers for strategy board and lifecycle."""

from __future__ import annotations

from pathlib import Path

from src.governance.strategy_board import StrategyBoardService
from src.ideas.manager import IdeaPipelineManager
from src.strategies.scoreboard import StrategyScoreboardService

from src.governance.lifecycle import (
    GateDefinition,
    GateResult,
    StrategyLifecycleOrchestrator,
)


def board_agenda(
    *,
    week: str,
    meeting_id: str,
    alpha_threshold: float = 70.0,
    include_stalled: bool = False,
    output_dir: Path = Path("reports/governance/strategy_board"),
) -> dict[str, object]:
    scoreboard = StrategyScoreboardService()
    watchlist = scoreboard.watchlist(threshold=alpha_threshold)
    blocked = []
    if include_stalled:
        pipeline = IdeaPipelineManager()
        summary = pipeline.summarize_pipeline()
        blocked = [{"strategy_id": idea_id} for idea_id in summary.get("stalled", [])]
    service = StrategyBoardService(output_dir=output_dir)
    path = service.generate_agenda(meeting_id=meeting_id, week=week, watchlist=watchlist, blocked=blocked)
    return {"status": "ok", "path": str(path), "watchlist": watchlist, "blocked": blocked}


def board_decision(
    *,
    meeting_id: str,
    strategy_id: str,
    decision: str,
    actor: str,
    notes: str | None = None,
) -> dict[str, object]:
    service = StrategyBoardService()
    entry = service.record_decision(
        meeting_id=meeting_id,
        strategy_id=strategy_id,
        decision=decision,
        actor=actor,
        notes=notes,
    )
    return {"status": "ok", "decision": entry.to_dict()}


def board_publish(
    *,
    meeting_id: str,
    profile_id: str,
    channel: str = "local",
    dry_run: bool = False,
) -> dict[str, object]:
    service = StrategyBoardService()
    return service.publish_summary(
        meeting_id=meeting_id, profile_id=profile_id, channel=channel, dry_run=dry_run
    )


def lifecycle_status(
    *, strategy_id: str | None, orchestrator: StrategyLifecycleOrchestrator | None = None
) -> dict[str, object]:
    orchestrator = orchestrator or StrategyLifecycleOrchestrator()
    if strategy_id:
        state = orchestrator.load_state(strategy_id)
        return {"status": "ok", "state": state.to_dict()}
    states = [state.to_dict() for state in orchestrator.list_states()]
    return {"status": "ok", "states": states}


def lifecycle_gates(
    *, orchestrator: StrategyLifecycleOrchestrator | None = None
) -> dict[str, object]:
    orchestrator = orchestrator or StrategyLifecycleOrchestrator()
    gates = [gate.to_dict() for gate in orchestrator.list_gates()]
    return {"status": "ok", "gates": gates}


def lifecycle_evaluate(
    *,
    strategy_id: str,
    gate_id: str,
    signals: dict[str, object],
    actor: str,
    force: bool = False,
    orchestrator: StrategyLifecycleOrchestrator | None = None,
) -> dict[str, object]:
    orchestrator = orchestrator or StrategyLifecycleOrchestrator()
    result = orchestrator.evaluate_gate(
        strategy_id=strategy_id,
        gate_id=gate_id,
        signals=signals,
        actor=actor,
        force=force,
    )
    return {"status": "ok", "result": result.to_dict()}


def lifecycle_history(
    *, strategy_id: str, orchestrator: StrategyLifecycleOrchestrator | None = None
) -> dict[str, object]:
    orchestrator = orchestrator or StrategyLifecycleOrchestrator()
    history_path = orchestrator.export_history(strategy_id=strategy_id)
    return {"status": "ok", "history_path": str(history_path)}


def lifecycle_simulate(
    *,
    strategy_id: str,
    scenario: str,
    orchestrator: StrategyLifecycleOrchestrator | None = None,
) -> dict[str, object]:
    orchestrator = orchestrator or StrategyLifecycleOrchestrator()
    result = orchestrator.simulate(strategy_id=strategy_id, scenario=scenario)
    return {"status": "ok", "result": result.to_dict()}


__all__ = [
    "board_agenda",
    "board_decision",
    "board_publish",
    "lifecycle_status",
    "lifecycle_gates",
    "lifecycle_evaluate",
    "lifecycle_history",
    "lifecycle_simulate",
    "GateDefinition",
    "GateResult",
]
