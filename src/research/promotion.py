"""Research promotion workflow helpers."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.compliance.risk_disclosure_enforcer import RiskDisclosureEnforcer
from src.ops.agenda import OPS_AGENDA_EVENT_LOG_PATH
from src.ops.evidence import EvidenceError, OpsEvidenceStore
from src.ops_readiness import OpsReadinessEvaluator
from src.research.experiment import ExperimentRun, ExperimentTrackerService
from src.research.pipeline import GateEvaluationResult, ResearchPipelineService, ValidationResult

DEFAULT_PROMOTION_DIR = Path("reports") / "research" / "promotion"
DEFAULT_EVENT_LOG = Path("logs") / "events" / "research_promotion.jsonl"
DEFAULT_AUDIT_LOG = Path("logs") / "audit" / "research_promotion.jsonl"
DEFAULT_PROMOTION_CHECKLIST_DIR = DEFAULT_PROMOTION_DIR / "checklists"
DEFAULT_PROMOTION_AUDIT = Path("logs") / "audit" / "promotion_gate.jsonl"
DEFAULT_VALIDATION_PLAYBOOK_DIR = Path("docs") / "validation_playbook"
DEFAULT_PROMOTION_PLAYBOOK = DEFAULT_VALIDATION_PLAYBOOK_DIR / "AC46_promotion_gate.yaml"
DEFAULT_PROMOTION_METRICS = Path("metrics") / "promotion_gate.jsonl"
DEFAULT_IDEA_ROOT = Path("research") / "ideas"
DEFAULT_ROLES_PATH = Path("config") / "roles.yaml"

EXPERIMENT_THRESHOLDS = {
    "pf_oos": 1.05,
    "sharpe": 0.8,
    "max_dd": 0.12,
    "trades": 30,
    "consistency": 0.6,
}


class PromotionError(RuntimeError):
    """Raised when promotion evaluation fails."""


@dataclass(slots=True)
class PipelinePromotionResult:
    strategy_id: str
    target_stage: str
    status: str
    gate: GateEvaluationResult
    validation: ValidationResult | None
    checklist_path: Path | None
    report_path: Path | None
    dry_run_path: Path | None

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "target_stage": self.target_stage,
            "status": self.status,
            "gate": self.gate.to_dict(),
            "validation": self.validation.to_dict() if self.validation else None,
            "checklist_path": str(self.checklist_path) if self.checklist_path else None,
            "report_path": str(self.report_path) if self.report_path else None,
            "dry_run_path": str(self.dry_run_path) if self.dry_run_path else None,
        }


def promote(
    *,
    strategy_id: str,
    target_stage: str,
    window: str,
    mode: str,
    suite_path: Path,
    metrics_path: Path | None,
    note: str | None,
    attachments: list[Path],
    dry_run: bool,
    output_dir: Path = DEFAULT_PROMOTION_DIR,
    event_log: Path = DEFAULT_EVENT_LOG,
    audit_log: Path = DEFAULT_AUDIT_LOG,
) -> PipelinePromotionResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    service = ResearchPipelineService(suite_path=suite_path)
    validation = service.run_validation(
        strategy_id=strategy_id,
        window=window,
        mode=mode,
        metrics_path=metrics_path,
    )
    gate = service.evaluate_gate(validation)
    status = "pass" if gate.status == "pass" else "blocked"

    date_stamp = _date_stamp()
    checklist_path = output_dir / f"{strategy_id}_{date_stamp}_checklist.md"
    dry_run_path = (
        output_dir / f"{strategy_id}_{date_stamp}_dryrun.json" if dry_run else None
    )
    report_path = None if dry_run else output_dir / f"{strategy_id}_{date_stamp}.md"

    _write_checklist(
        checklist_path,
        strategy_id=strategy_id,
        target_stage=target_stage,
        gate=gate,
        validation=validation,
        attachments=attachments,
        note=note,
    )
    if dry_run_path:
        dry_run_path.write_text(
            json.dumps(
                {
                    "strategy_id": strategy_id,
                    "target_stage": target_stage,
                    "status": status,
                    "gate": gate.to_dict(),
                    "validation": validation.to_dict(),
                    "attachments": [str(p) for p in attachments],
                    "note": note,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    if report_path:
        _write_report(
            report_path,
            strategy_id=strategy_id,
            target_stage=target_stage,
            status=status,
            gate=gate,
            validation=validation,
            attachments=attachments,
            note=note,
        )

    _append_event(
        event_log,
        {
            "event": "research.promotion",
            "ts": _utcnow_iso(),
            "strategy_id": strategy_id,
            "target_stage": target_stage,
            "status": status,
            "dry_run": dry_run,
            "gate": gate.to_dict(),
            "validation_status": validation.status,
            "checklist_path": str(checklist_path),
            "report_path": str(report_path) if report_path else None,
        },
    )
    _append_event(
        audit_log,
        {
            "event": "audit.research_promotion",
            "ts": _utcnow_iso(),
            "strategy_id": strategy_id,
            "target_stage": target_stage,
            "status": status,
            "dry_run": dry_run,
            "note": note,
            "attachments": [str(p) for p in attachments],
            "validation_status": validation.status,
        },
    )

    return PipelinePromotionResult(
        strategy_id=strategy_id,
        target_stage=target_stage,
        status=status,
        gate=gate,
        validation=validation,
        checklist_path=checklist_path,
        report_path=report_path,
        dry_run_path=dry_run_path,
    )


def _write_checklist(
    path: Path,
    *,
    strategy_id: str,
    target_stage: str,
    gate: GateEvaluationResult,
    validation: ValidationResult,
    attachments: list[Path],
    note: str | None,
) -> None:
    lines = [
        f"# Promotion Checklist ({strategy_id})",
        "",
        f"- Target: {target_stage}",
        f"- Gate: {gate.status}",
        f"- Validation: {validation.status}",
        "",
        "## Evidence",
    ]
    if attachments:
        lines.extend([f"- {path}" for path in attachments])
    else:
        lines.append("- (none)")
    if gate.reasons:
        lines.append("")
        lines.append("## Gate Failures")
        lines.extend([f"- {reason}" for reason in gate.reasons])
    if note:
        lines.append("")
        lines.append("## Notes")
        lines.append(note)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(
    path: Path,
    *,
    strategy_id: str,
    target_stage: str,
    status: str,
    gate: GateEvaluationResult,
    validation: ValidationResult,
    attachments: list[Path],
    note: str | None,
) -> None:
    lines = [
        f"# Promotion Result ({strategy_id})",
        "",
        f"- Target: {target_stage}",
        f"- Status: {status}",
        f"- Validation: {validation.status}",
        f"- Gate: {gate.status}",
        "",
        "## Attachments",
    ]
    if attachments:
        lines.extend([f"- {path}" for path in attachments])
    else:
        lines.append("- (none)")
    if note:
        lines.append("")
        lines.append("## Notes")
        lines.append(note)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_event(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _date_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


@dataclass(slots=True)
class EvidenceLink:
    path: str
    hash: str | None
    type: str
    validated_at: str | None = None
    validator: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "hash": self.hash,
            "type": self.type,
            "validated_at": self.validated_at,
            "validator": self.validator,
        }


@dataclass(slots=True)
class ChecklistItem:
    item_id: str
    description: str
    source: str
    status: str
    evidence_refs: list[EvidenceLink]
    threshold: str | None = None
    auto_fix_hint: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "description": self.description,
            "source": self.source,
            "status": self.status,
            "evidence_refs": [ref.to_dict() for ref in self.evidence_refs],
            "threshold": self.threshold,
            "auto_fix_hint": self.auto_fix_hint,
        }


@dataclass(slots=True)
class PromotionChecklist:
    strategy_id: str
    target_stage: str
    items: list[ChecklistItem]
    last_evaluated_at: str | None
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "target_stage": self.target_stage,
            "items": [item.to_dict() for item in self.items],
            "last_evaluated_at": self.last_evaluated_at,
            "status": self.status,
        }


@dataclass(slots=True)
class PromotionResult:
    status: str
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return {"status": self.status, "reasons": list(self.reasons)}


@dataclass(slots=True)
class PromotionReceipt:
    strategy_id: str
    target_stage: str
    status: str
    reasons: list[str]
    checklist: PromotionChecklist
    experiment_run_ids: list[str]
    validation_playbook_ids: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "target_stage": self.target_stage,
            "status": self.status,
            "reasons": list(self.reasons),
            "checklist": self.checklist.to_dict(),
            "experiment_run_ids": list(self.experiment_run_ids),
            "validation_playbook_ids": list(self.validation_playbook_ids),
        }


class PromotionChecklistService:
    """Assemble and evaluate promotion checklists."""

    def __init__(
        self,
        *,
        idea_root: Path = DEFAULT_IDEA_ROOT,
        validation_playbook_dir: Path = DEFAULT_VALIDATION_PLAYBOOK_DIR,
        checklist_dir: Path = DEFAULT_PROMOTION_CHECKLIST_DIR,
        audit_log: Path = DEFAULT_PROMOTION_AUDIT,
        metrics_path: Path = DEFAULT_PROMOTION_METRICS,
        agenda_event_log: Path = OPS_AGENDA_EVENT_LOG_PATH,
        roles_path: Path = DEFAULT_ROLES_PATH,
        experiment_tracker: ExperimentTrackerService | None = None,
        ops_readiness: OpsReadinessEvaluator | None = None,
        risk_enforcer: RiskDisclosureEnforcer | None = None,
        evidence_store: OpsEvidenceStore | None = None,
    ) -> None:
        self._idea_root = idea_root
        self._validation_playbook_dir = validation_playbook_dir
        self._checklist_dir = checklist_dir
        self._audit_log = audit_log
        self._metrics_path = metrics_path
        self._agenda_event_log = agenda_event_log
        self._roles_path = roles_path
        self._experiment_tracker = experiment_tracker or ExperimentTrackerService()
        self._ops_readiness = ops_readiness or OpsReadinessEvaluator()
        self._risk_enforcer = risk_enforcer or RiskDisclosureEnforcer()
        self._evidence_store = evidence_store or OpsEvidenceStore()

    def load(self, strategy_id: str, target_stage: str) -> PromotionChecklist:
        manual_overrides = self._load_manual_overrides(strategy_id, target_stage)
        items: list[ChecklistItem] = []
        items.extend(self._load_stage_items(strategy_id, target_stage, manual_overrides))
        experiment_run = self._experiment_tracker.load_latest_run(strategy_id)
        items.extend(self._load_experiment_items(experiment_run, manual_overrides))
        items.extend(self._load_validation_items(strategy_id, target_stage, manual_overrides))
        items.extend(self._load_risk_items(manual_overrides))
        items.extend(self._load_ops_items(manual_overrides))
        status = _summarize_status(items)
        return PromotionChecklist(
            strategy_id=strategy_id,
            target_stage=target_stage,
            items=items,
            last_evaluated_at=None,
            status=status,
        )

    def evaluate(
        self,
        checklist: PromotionChecklist,
    ) -> PromotionResult:
        reasons = [item.item_id for item in checklist.items if item.status == "fail"]
        if any(item.status == "manual_review" for item in checklist.items):
            status = "manual_review"
        elif reasons:
            status = "fail"
        else:
            status = "pass"
        checklist.status = status
        checklist.last_evaluated_at = _utcnow_iso()
        return PromotionResult(status=status, reasons=reasons)

    def record_manual_review(
        self,
        *,
        strategy_id: str,
        target_stage: str,
        item_id: str,
        reviewer: str,
        note: str | None,
        evidence: list[Path] | None,
    ) -> PromotionChecklist:
        if not _actor_has_role(reviewer, "promotion_reviewer", self._roles_path):
            raise PermissionError("reviewer lacks promotion_reviewer role")
        checklist = self.load(strategy_id, target_stage)
        item = next((entry for entry in checklist.items if entry.item_id == item_id), None)
        if item is None:
            raise PromotionError(f"item not found: {item_id}")
        item.status = "pass"
        item.auto_fix_hint = None
        item.evidence_refs.extend(_evidence_links(evidence or [], reviewer=reviewer))
        checklist.status = _summarize_status(checklist.items)
        checklist.last_evaluated_at = _utcnow_iso()
        self._store_checklist(strategy_id, target_stage, checklist)
        self._append_audit(
            {
                "event": "audit.promotion_manual_review",
                "strategy_id": strategy_id,
                "target_stage": target_stage,
                "item_id": item_id,
                "reviewer": reviewer,
                "note": note,
                "evidence": [str(path) for path in evidence or []],
            }
        )
        return checklist

    def promote(
        self,
        strategy_id: str,
        target_stage: str,
        *,
        actor: str | None = None,
        dry_run: bool = False,
        override: bool = False,
        runbook_ref: str = "STRAT-PROMOTE-01",
    ) -> PromotionReceipt:
        started = time.perf_counter()
        checklist = self.load(strategy_id, target_stage)
        result = self.evaluate(checklist)
        checklist_path = self._store_checklist(strategy_id, target_stage, checklist)
        status = "pass" if result.status == "pass" else "blocked"
        reasons = list(result.reasons)
        if status == "blocked" and override:
            if actor is None or not _actor_has_role(actor, "promotion_override", self._roles_path):
                raise PermissionError("actor lacks promotion_override role")
            status = "pass"
            reasons = ["override"]
        experiment_run_ids = _experiment_run_ids(checklist.items)
        validation_playbook_ids = _validation_playbook_ids(checklist.items)
        consent_reference_id = self._risk_enforcer.enforce(
            action="promotion_gate", dry_run=True
        ).consent_reference_id
        if not dry_run:
            duration_sec = round(time.perf_counter() - started, 3)
            self._append_metrics(
                {
                    "strategy_id": strategy_id,
                    "target_stage": target_stage,
                    "status": status,
                    "failed_items": reasons,
                    "duration_sec": duration_sec,
                    "experiment_runs_used": len(experiment_run_ids),
                    "validation_refs_missing": _validation_missing_count(checklist.items),
                }
            )
            evidence_entry = None
            try:
                evidence_entry = self._evidence_store.register(
                    category="promotion_gate",
                    artifact=checklist_path,
                    runbook_refs=[runbook_ref],
                    validation_playbook_id="AC46_promotion_gate",
                    notes=f"strategy={strategy_id} target={target_stage} status={status}",
                )
            except EvidenceError:
                evidence_entry = None
            self._append_audit(
                {
                    "event": "audit.promotion_requested",
                    "strategy_id": strategy_id,
                    "target_stage": target_stage,
                    "actor": actor,
                    "runbook_ref": runbook_ref,
                    "consent_reference_id": consent_reference_id,
                    "experiment_run_ids": experiment_run_ids,
                    "validation_playbook_ids": validation_playbook_ids,
                    "checklist_path": str(checklist_path),
                    "evidence_sha256": evidence_entry.sha256 if evidence_entry else None,
                }
            )
            self._append_audit(
                {
                    "event": "audit.promotion_approved"
                    if status == "pass"
                    else "audit.promotion_blocked",
                    "strategy_id": strategy_id,
                    "target_stage": target_stage,
                    "actor": actor,
                    "status": status,
                    "reasons": reasons,
                    "runbook_ref": runbook_ref,
                    "consent_reference_id": consent_reference_id,
                    "experiment_run_ids": experiment_run_ids,
                    "validation_playbook_ids": validation_playbook_ids,
                    "override": override,
                    "checklist_path": str(checklist_path),
                    "evidence_sha256": evidence_entry.sha256 if evidence_entry else None,
                }
            )
            self._append_validation_playbook(
                {
                    "strategy_id": strategy_id,
                    "target_stage": target_stage,
                    "status": status,
                    "reasons": reasons,
                    "actor": actor,
                    "runbook_ref": runbook_ref,
                    "consent_reference_id": consent_reference_id,
                    "experiment_run_ids": experiment_run_ids,
                    "validation_playbook_ids": validation_playbook_ids,
                    "checklist_path": str(checklist_path),
                    "evidence_sha256": evidence_entry.sha256 if evidence_entry else None,
                }
            )
            if status == "blocked":
                self._append_ops_agenda_event(
                    {
                        "event": "promotion.blocked",
                        "strategy_id": strategy_id,
                        "target_stage": target_stage,
                        "reasons": reasons,
                        "runbook_ref": runbook_ref,
                    }
                )
        return PromotionReceipt(
            strategy_id=strategy_id,
            target_stage=target_stage,
            status=status,
            reasons=reasons,
            checklist=checklist,
            experiment_run_ids=experiment_run_ids,
            validation_playbook_ids=validation_playbook_ids,
        )

    def _load_stage_items(
        self,
        strategy_id: str,
        target_stage: str,
        manual_overrides: dict[str, list[EvidenceLink]],
    ) -> list[ChecklistItem]:
        checklist_path = self._idea_root / str(strategy_id) / "checklists" / f"{target_stage}.yaml"
        if not checklist_path.exists():
            return []
        payload = _load_yaml(checklist_path)
        if not isinstance(payload, Mapping):
            return []
        items: list[ChecklistItem] = []
        for entry in payload.get("items") or []:
            if not isinstance(entry, Mapping):
                continue
            item_id = str(entry.get("item_id") or "")
            if not item_id:
                continue
            if item_id.startswith("validation:"):
                continue
            raw_status = str(entry.get("status") or "todo")
            if raw_status in {"manual_review", "review"}:
                status = "manual_review"
            else:
                status = "pass" if raw_status in {"done", "pass"} else "fail"
            evidence_refs = _evidence_links(
                [_optional_path(entry.get("evidence_path"))] if entry.get("evidence_path") else []
            )
            if item_id in manual_overrides:
                status = "pass"
                evidence_refs.extend(manual_overrides[item_id])
            items.append(
                ChecklistItem(
                    item_id=item_id,
                    description=str(entry.get("description") or ""),
                    source="runbook",
                    status=status,
                    evidence_refs=evidence_refs,
                )
            )
        return items

    def _load_experiment_items(
        self,
        experiment_run: ExperimentRun | None,
        manual_overrides: dict[str, list[EvidenceLink]],
    ) -> list[ChecklistItem]:
        items: list[ChecklistItem] = []
        if experiment_run is None:
            items.append(
                ChecklistItem(
                    item_id="experiment.run_available",
                    description="Experiment run completed",
                    source="experiment",
                    status="fail",
                    evidence_refs=[],
                    auto_fix_hint="tradectl research experiment run",
                )
            )
            return items
        run_id = experiment_run.run_id
        status = experiment_run.status
        if status != "completed":
            items.append(
                ChecklistItem(
                    item_id="experiment.run_status",
                    description=f"Experiment status={status}",
                    source="experiment",
                    status="fail",
                    evidence_refs=[],
                    auto_fix_hint="tradectl research experiment run",
                )
            )
        for metric, threshold in EXPERIMENT_THRESHOLDS.items():
            value = experiment_run.metrics.get(metric)
            passed = _metric_passes(metric, value, threshold)
            item_id = f"experiment.{metric}"
            item_status = "pass" if passed else "fail"
            auto_fix = None if passed else "tradectl research experiment run"
            evidence_refs = manual_overrides.get(item_id, [])
            if evidence_refs:
                item_status = "pass"
                auto_fix = None
            items.append(
                ChecklistItem(
                    item_id=item_id,
                    description=f"{metric} threshold check",
                    source="experiment",
                    status=item_status,
                    evidence_refs=list(evidence_refs),
                    threshold=f"{threshold}",
                    auto_fix_hint=auto_fix,
                )
            )
        items.append(
            ChecklistItem(
                item_id="experiment.run_id",
                description="Experiment run id recorded",
                source="experiment",
                status="pass",
                evidence_refs=[EvidenceLink(path=f"run:{run_id}", hash=None, type="metrics")],
            )
        )
        return items

    def _load_validation_items(
        self,
        strategy_id: str,
        target_stage: str,
        manual_overrides: dict[str, list[EvidenceLink]],
    ) -> list[ChecklistItem]:
        checklist_path = self._idea_root / str(strategy_id) / "checklists" / f"{target_stage}.yaml"
        payload = _load_yaml(checklist_path)
        if not isinstance(payload, Mapping):
            return []
        items: list[ChecklistItem] = []
        for entry in payload.get("items") or []:
            if not isinstance(entry, Mapping):
                continue
            raw_id = str(entry.get("item_id") or "")
            if not raw_id.startswith("validation:"):
                continue
            playbook_id = raw_id.split("validation:", 1)[-1]
            playbook_path = self._validation_playbook_dir / f"{playbook_id}.yaml"
            status = "pass" if playbook_path.exists() else "fail"
            auto_fix_hint = None if status == "pass" else f"make check-validation --category {playbook_id}"
            evidence_refs = manual_overrides.get(raw_id, [])
            if evidence_refs:
                status = "pass"
                auto_fix_hint = None
            items.append(
                ChecklistItem(
                    item_id=raw_id,
                    description=f"Validation playbook {playbook_id}",
                    source="validation_playbook",
                    status=status,
                    evidence_refs=list(evidence_refs),
                    auto_fix_hint=auto_fix_hint,
                )
            )
        return items

    def _load_risk_items(
        self,
        manual_overrides: dict[str, list[EvidenceLink]],
    ) -> list[ChecklistItem]:
        decision = self._risk_enforcer.enforce(action="promotion_gate", dry_run=True)
        status = "pass" if decision.decision == "allow" else "fail"
        auto_fix = None if status == "pass" else "tradectl compliance risk-disclosure enforce"
        evidence_refs = manual_overrides.get("risk_consent_valid", [])
        if evidence_refs:
            status = "pass"
            auto_fix = None
        return [
            ChecklistItem(
                item_id="risk_consent_valid",
                description="Risk consent accepted",
                source="risk",
                status=status,
                evidence_refs=list(evidence_refs),
                auto_fix_hint=auto_fix,
            )
        ]

    def _load_ops_items(
        self,
        manual_overrides: dict[str, list[EvidenceLink]],
    ) -> list[ChecklistItem]:
        result = self._ops_readiness.evaluate()
        status = "pass" if result.score >= 80 else "manual_review"
        auto_fix = None if status == "pass" else "tradectl ops readiness"
        evidence_refs = manual_overrides.get("ops_readiness", [])
        if evidence_refs:
            status = "pass"
            auto_fix = None
        return [
            ChecklistItem(
                item_id="ops_readiness",
                description=f"Ops readiness score {result.score:.1f}",
                source="ops",
                status=status,
                evidence_refs=list(evidence_refs),
                auto_fix_hint=auto_fix,
            )
        ]

    def _store_checklist(
        self,
        strategy_id: str,
        target_stage: str,
        checklist: PromotionChecklist,
    ) -> Path:
        self._checklist_dir.mkdir(parents=True, exist_ok=True)
        path = self._checklist_dir / f"{strategy_id}_{target_stage}.json"
        path.write_text(json.dumps(checklist.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _load_manual_overrides(
        self,
        strategy_id: str,
        target_stage: str,
    ) -> dict[str, list[EvidenceLink]]:
        path = self._checklist_dir / f"{strategy_id}_{target_stage}.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        overrides: dict[str, list[EvidenceLink]] = {}
        for item in payload.get("items") or []:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("status")) != "pass":
                continue
            evidence = []
            for ref in item.get("evidence_refs") or []:
                if not isinstance(ref, Mapping):
                    continue
                evidence.append(
                    EvidenceLink(
                        path=str(ref.get("path") or ""),
                        hash=ref.get("hash"),
                        type=str(ref.get("type") or "signoff"),
                        validated_at=ref.get("validated_at"),
                        validator=ref.get("validator"),
                    )
                )
            if evidence:
                overrides[str(item.get("item_id") or "")] = evidence
        return overrides

    def _append_audit(self, payload: Mapping[str, Any]) -> None:
        self._audit_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self._audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")

    def _append_metrics(self, payload: Mapping[str, Any]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")

    def _append_validation_playbook(self, payload: Mapping[str, Any]) -> None:
        self._validation_playbook_dir.mkdir(parents=True, exist_ok=True)
        playbook_path = self._validation_playbook_dir / DEFAULT_PROMOTION_PLAYBOOK.name
        data = {}
        if playbook_path.exists():
            try:
                data = yaml.safe_load(playbook_path.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        entries = list(data.get("entries") or [])
        entries.append({"ts": _utcnow_iso(), **payload})
        data.update(
            {
                "validation_playbook_id": "AC46_promotion_gate",
                "category": "research_promotion",
                "entries": entries,
            }
        )
        playbook_path.write_text(_dump_yaml(data), encoding="utf-8")

    def _append_ops_agenda_event(self, payload: Mapping[str, Any]) -> None:
        self._agenda_event_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self._agenda_event_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")


def _load_yaml(path: Path) -> Mapping[str, Any] | list[Any] | str:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _summarize_status(items: list[ChecklistItem]) -> str:
    if any(item.status == "fail" for item in items):
        return "fail"
    if any(item.status == "manual_review" for item in items):
        return "manual_review"
    return "pass"


def _metric_passes(metric: str, value: float | None, threshold: float) -> bool:
    if value is None:
        return False
    if metric == "max_dd":
        return value <= threshold
    return value >= threshold


def _evidence_links(paths: list[Path | None], *, reviewer: str | None = None) -> list[EvidenceLink]:
    links: list[EvidenceLink] = []
    for path in paths:
        if path is None:
            continue
        links.append(
            EvidenceLink(
                path=str(path),
                hash=None,
                type="signoff" if reviewer else "report",
                validated_at=_utcnow_iso() if reviewer else None,
                validator=reviewer,
            )
        )
    return links


def _experiment_run_ids(items: list[ChecklistItem]) -> list[str]:
    run_ids = []
    for item in items:
        if item.item_id == "experiment.run_id":
            for ref in item.evidence_refs:
                if ref.path.startswith("run:"):
                    run_ids.append(ref.path.split("run:", 1)[-1])
    return run_ids


def _validation_playbook_ids(items: list[ChecklistItem]) -> list[str]:
    ids = []
    for item in items:
        if item.source == "validation_playbook" and item.item_id.startswith("validation:"):
            ids.append(item.item_id.split("validation:", 1)[-1])
    return ids


def _actor_has_role(actor: str, role: str, roles_path: Path) -> bool:
    if not roles_path.exists():
        return False
    payload = yaml.safe_load(roles_path.read_text(encoding="utf-8")) or {}
    roles = payload.get("roles") if isinstance(payload, dict) else {}
    entry = roles.get(role) if isinstance(roles, dict) else None
    members = entry.get("members") if isinstance(entry, dict) else []
    for member in members or []:
        if not isinstance(member, Mapping):
            continue
        if member.get("principal_id") == actor:
            return True
    return False


def _optional_path(value: object | None) -> Path | None:
    if not value:
        return None
    return Path(str(value))


def _validation_missing_count(items: list[ChecklistItem]) -> int:
    return sum(
        1
        for item in items
        if item.source == "validation_playbook" and item.status != "pass"
    )


def _dump_yaml(payload: Mapping[str, object]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        return dumper(dict(payload), sort_keys=False, allow_unicode=True)
    return "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = [
    "PipelinePromotionResult",
    "PromotionResult",
    "PromotionReceipt",
    "PromotionChecklist",
    "ChecklistItem",
    "EvidenceLink",
    "PromotionChecklistService",
    "PromotionError",
    "promote",
]
