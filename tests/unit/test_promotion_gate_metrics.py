import json
from dataclasses import dataclass
from pathlib import Path

from src.ops.evidence import OpsEvidenceStore
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
    consent_reference_id: str


class _RiskEnforcerStub:
    def __init__(self, decision: str = "allow", consent_reference_id: str = "consent-1") -> None:
        self._decision = decision
        self._consent_reference_id = consent_reference_id

    def enforce(self, *, action: str, dry_run: bool = False) -> _RiskDecision:
        return _RiskDecision(decision=self._decision, consent_reference_id=self._consent_reference_id)


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
                "item_id": "validation:AC46_promotion_gate",
                "description": "Validation playbook",
                "status": "todo",
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_yaml(payload), encoding="utf-8")


def test_promotion_records_metrics_and_playbook(tmp_path: Path) -> None:
    idea_root = tmp_path / "ideas"
    checklist_path = idea_root / "strat-a" / "checklists" / "paper.yaml"
    _write_checklist(checklist_path)
    playbook_dir = tmp_path / "playbooks"
    playbook_dir.mkdir(parents=True, exist_ok=True)
    (playbook_dir / "AC46_promotion_gate.yaml").write_text(
        "validation_playbook_id: AC46_promotion_gate\ncategory: research_promotion\nentries: []\n",
        encoding="utf-8",
    )

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
    evidence_store = OpsEvidenceStore(
        ledger_path=tmp_path / "evidence.jsonl",
        playbook_dir=playbook_dir,
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
    )
    service = PromotionChecklistService(
        idea_root=idea_root,
        validation_playbook_dir=playbook_dir,
        checklist_dir=tmp_path / "checklists",
        audit_log=tmp_path / "audit.jsonl",
        metrics_path=tmp_path / "metrics.jsonl",
        agenda_event_log=tmp_path / "agenda.jsonl",
        experiment_tracker=_ExperimentTrackerStub(run),
        ops_readiness=_OpsReadinessStub(score=90),
        risk_enforcer=_RiskEnforcerStub("allow"),
        evidence_store=evidence_store,
        roles_path=tmp_path / "roles.yaml",
    )

    receipt = service.promote("strat-a", "paper", actor="alice", dry_run=False)

    assert receipt.status == "pass"
    metrics_text = (tmp_path / "metrics.jsonl").read_text(encoding="utf-8")
    assert "strategy_id" in metrics_text
    playbook_text = (playbook_dir / "AC46_promotion_gate.yaml").read_text(encoding="utf-8")
    assert "strat-a" in playbook_text
    evidence_text = (tmp_path / "evidence.jsonl").read_text(encoding="utf-8")
    assert "promotion_gate" in evidence_text
