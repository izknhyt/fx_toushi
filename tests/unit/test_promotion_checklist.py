import json
from dataclasses import dataclass
from pathlib import Path

from src.research.experiment import ExperimentRun, ExperimentTrackerService
from src.research.promotion import PromotionChecklistService


def _dump_yaml(payload: dict) -> str:
    return "# JSON\n" + json.dumps(payload)


@dataclass(slots=True)
class _OpsResult:
    score: float


class _OpsReadinessStub:
    def __init__(self, score: float) -> None:
        self._score = score

    def evaluate(self) -> _OpsResult:
        return _OpsResult(score=self._score)


@dataclass(slots=True)
class _RiskDecision:
    decision: str


class _RiskEnforcerStub:
    def __init__(self, decision: str = "allow") -> None:
        self._decision = decision

    def enforce(self, *, action: str, dry_run: bool = False) -> _RiskDecision:
        return _RiskDecision(decision=self._decision)


class _ExperimentTrackerStub(ExperimentTrackerService):
    def __init__(self, run: ExperimentRun | None) -> None:
        self._run = run

    def load_latest_run(self, strategy_id: str) -> ExperimentRun | None:
        return self._run


def _write_checklist(path: Path) -> None:
    payload = {
        "stage": "paper",
        "items": [
            {
                "item_id": "runbook.ready",
                "description": "Runbook evidence attached",
                "status": "done",
                "evidence_path": "reports/research/foo.md",
            },
            {
                "item_id": "validation:AC99_promo",
                "description": "Validation playbook",
                "status": "todo",
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_yaml(payload), encoding="utf-8")


def test_checklist_loads_experiment_and_validation(tmp_path: Path) -> None:
    idea_root = tmp_path / "ideas"
    checklist_path = idea_root / "strat-a" / "checklists" / "paper.yaml"
    _write_checklist(checklist_path)
    playbook_dir = tmp_path / "playbooks"
    playbook_dir.mkdir(parents=True, exist_ok=True)
    (playbook_dir / "AC99_promo.yaml").write_text("validation_playbook_id: AC99_promo\n", encoding="utf-8")

    run = ExperimentRun(
        run_id="run-1",
        experiment_id="exp-1",
        strategy_id="strat-a",
        run_type="backtest",
        parameters={},
        dataset_manifest_hash="hash-1",
        code_revision="rev-1",
        status="completed",
        metrics={"pf_oos": 1.2, "sharpe": 0.9, "max_dd": 0.08, "trades": 40, "consistency": 0.7},
        artifacts=[],
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:00Z",
    )
    service = PromotionChecklistService(
        idea_root=idea_root,
        validation_playbook_dir=playbook_dir,
        checklist_dir=tmp_path / "checklists",
        experiment_tracker=_ExperimentTrackerStub(run),
        ops_readiness=_OpsReadinessStub(score=90),
        risk_enforcer=_RiskEnforcerStub("allow"),
        roles_path=tmp_path / "roles.yaml",
    )

    checklist = service.load("strat-a", "paper")

    ids = {item.item_id for item in checklist.items}
    assert "runbook.ready" in ids
    assert "validation:AC99_promo" in ids
    assert "experiment.pf_oos" in ids
    assert checklist.status in {"pass", "manual_review", "fail"}


def test_ops_readiness_manual_review(tmp_path: Path) -> None:
    idea_root = tmp_path / "ideas"
    checklist_path = idea_root / "strat-b" / "checklists" / "paper.yaml"
    _write_checklist(checklist_path)
    playbook_dir = tmp_path / "playbooks"
    playbook_dir.mkdir(parents=True, exist_ok=True)
    (playbook_dir / "AC99_promo.yaml").write_text("validation_playbook_id: AC99_promo\n", encoding="utf-8")

    service = PromotionChecklistService(
        idea_root=idea_root,
        validation_playbook_dir=playbook_dir,
        checklist_dir=tmp_path / "checklists",
        experiment_tracker=_ExperimentTrackerStub(None),
        ops_readiness=_OpsReadinessStub(score=60),
        risk_enforcer=_RiskEnforcerStub("allow"),
        roles_path=tmp_path / "roles.yaml",
    )

    checklist = service.load("strat-b", "paper")
    ops_item = next(item for item in checklist.items if item.item_id == "ops_readiness")
    assert ops_item.status == "manual_review"


def test_manual_review_requires_role(tmp_path: Path) -> None:
    idea_root = tmp_path / "ideas"
    checklist_path = idea_root / "strat-c" / "checklists" / "paper.yaml"
    _write_checklist(checklist_path)
    roles_path = tmp_path / "roles.yaml"
    roles_path.write_text(
        _dump_yaml(
            {
                "roles": {
                    "promotion_reviewer": {
                        "members": [{"principal_id": "alice"}],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    service = PromotionChecklistService(
        idea_root=idea_root,
        validation_playbook_dir=tmp_path / "playbooks",
        checklist_dir=tmp_path / "checklists",
        experiment_tracker=_ExperimentTrackerStub(None),
        ops_readiness=_OpsReadinessStub(score=90),
        risk_enforcer=_RiskEnforcerStub("allow"),
        roles_path=roles_path,
    )

    try:
        service.record_manual_review(
            strategy_id="strat-c",
            target_stage="paper",
            item_id="runbook.ready",
            reviewer="bob",
            note="no role",
            evidence=[],
        )
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass

    checklist = service.record_manual_review(
        strategy_id="strat-c",
        target_stage="paper",
        item_id="runbook.ready",
        reviewer="alice",
        note="reviewed",
        evidence=[],
    )
    item = next(entry for entry in checklist.items if entry.item_id == "runbook.ready")
    assert item.status == "pass"
