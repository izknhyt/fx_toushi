from __future__ import annotations

from pathlib import Path

import pytest

from src.governance.lifecycle import StrategyLifecycleOrchestrator


def _write_roles(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "roles:",
                "  lifecycle_override:",
                "    members:",
                "      - principal_id: user:override",
                "        type: user",
                "        display_name: Override User",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_lifecycle_gate_evaluation(tmp_path: Path) -> None:
    roles_path = tmp_path / "roles.yaml"
    _write_roles(roles_path)
    orchestrator = StrategyLifecycleOrchestrator(
        state_dir=tmp_path / "state",
        history_log=tmp_path / "history.jsonl",
        audit_log=tmp_path / "audit.jsonl",
        metrics_path=tmp_path / "metrics.jsonl",
        roles_path=roles_path,
    )
    result = orchestrator.evaluate_gate(
        strategy_id="strat_a",
        gate_id="gate.paper_promotion",
        signals={
            "idea.stage.screening": True,
            "strategy_board.decision.approve": True,
            "alpha_score": 80,
            "ops_readiness_score": 85,
        },
        actor="user:override",
        force=False,
    )
    assert result.status in {"pass", "fail"}


def test_lifecycle_force_requires_role(tmp_path: Path) -> None:
    roles_path = tmp_path / "roles.yaml"
    _write_roles(roles_path)
    orchestrator = StrategyLifecycleOrchestrator(
        state_dir=tmp_path / "state",
        history_log=tmp_path / "history.jsonl",
        audit_log=tmp_path / "audit.jsonl",
        metrics_path=tmp_path / "metrics.jsonl",
        roles_path=roles_path,
    )
    with pytest.raises(PermissionError):
        orchestrator.evaluate_gate(
            strategy_id="strat_a",
            gate_id="gate.paper_promotion",
            signals={},
            actor="user:unknown",
            force=True,
        )
