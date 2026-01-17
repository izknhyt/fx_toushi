"""Idea pipeline manager implementation (M2)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.governance.model_risk import ModelRiskRegisterService, ModelRiskSchemaError
from src.ops.evidence import OpsEvidenceStore
from src.ops_readiness.evaluator import OpsReadinessEvaluator
from src.utils.hashing import sha256_path

DEFAULT_IDEA_ROOT = Path("research") / "ideas"
DEFAULT_CONFIG_PATH = Path("config") / "idea_pipeline.yaml"
DEFAULT_FEATURE_FLAGS_PATH = Path("config") / "feature_flags.yaml"
DEFAULT_ROLES_PATH = Path("config") / "roles.yaml"
DEFAULT_EVENT_LOG = Path("logs") / "events" / "idea_pipeline.jsonl"
DEFAULT_AUDIT_LOG = Path("logs") / "audit" / "idea_pipeline.jsonl"
DEFAULT_METRICS_PATH = Path("metrics") / "idea_pipeline.jsonl"

OPS_READINESS_MIN_SCORE = 75


class IdeaPipelineError(RuntimeError):
    """Base error for idea pipeline operations."""


class IdeaNotFoundError(IdeaPipelineError):
    """Raised when an idea record cannot be located."""


class StageDefinitionMissing(IdeaPipelineError):
    """Raised when a stage definition is missing from config."""


class ChecklistIncompleteError(IdeaPipelineError):
    """Raised when checklist completion is insufficient for a transition."""


class EvidenceMissingError(IdeaPipelineError):
    """Raised when required evidence is missing."""


class MetricsGapError(IdeaPipelineError):
    """Raised when required metrics are below thresholds."""


@dataclass(slots=True)
class EvidenceSpec:
    evidence_id: str
    path: str
    hash_required: bool
    validation_playbook_id: str | None
    expires_in_days: int | None


@dataclass(slots=True)
class StageDefinition:
    stage: str
    checklist_template: Path
    required_evidence: list[EvidenceSpec]
    minimum_metrics: dict[str, float]
    min_weeks_at_stage: int
    feature_flags: list[str]


@dataclass(slots=True)
class StageChecklistItem:
    item_id: str
    description: str
    owner_role: str | None
    status: str
    evidence_path: str | None = None
    last_update_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "description": self.description,
            "owner_role": self.owner_role,
            "status": self.status,
            "evidence_path": self.evidence_path,
            "last_update_at": self.last_update_at,
        }


@dataclass(slots=True)
class StageChecklist:
    stage: str
    items: list[StageChecklistItem] = field(default_factory=list)

    def completion_pct(self) -> float:
        if not self.items:
            return 0.0
        done = sum(1 for item in self.items if item.status == "done")
        return round((done / len(self.items)) * 100, 2)

    def missing_items(self) -> list[StageChecklistItem]:
        return [item for item in self.items if item.status != "done"]

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "completion_pct": self.completion_pct(),
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(slots=True)
class IdeaRecord:
    idea_id: str
    title: str
    owner: str | None
    strategy_refs: list[str]
    current_stage: str
    created_at: str
    tags: list[str]
    path: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "idea_id": self.idea_id,
            "title": self.title,
            "owner": self.owner,
            "strategy_refs": list(self.strategy_refs),
            "current_stage": self.current_stage,
            "created_at": self.created_at,
            "tags": list(self.tags),
            "path": str(self.path),
        }


@dataclass(slots=True)
class StageEvaluationResult:
    idea_id: str
    from_stage: str
    to_stage: str
    allowed: bool
    reasons: list[str]
    actions_required: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "idea_id": self.idea_id,
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "actions_required": list(self.actions_required),
        }


@dataclass(slots=True)
class ChecklistUpdateReceipt:
    idea_id: str
    stage: str
    item_id: str
    status: str
    evidence_path: str | None
    updated_at: str


@dataclass(slots=True)
class ArchiveReceipt:
    idea_id: str
    previous_stage: str
    archived_at: str
    reason: str


class IdeaPipelineManager:
    """Manage idea stage transitions, checklists, and evidence."""

    def __init__(
        self,
        *,
        root: Path = DEFAULT_IDEA_ROOT,
        config_path: Path = DEFAULT_CONFIG_PATH,
        feature_flags_path: Path = DEFAULT_FEATURE_FLAGS_PATH,
        roles_path: Path = DEFAULT_ROLES_PATH,
        evidence_store: OpsEvidenceStore | None = None,
        ops_readiness: OpsReadinessEvaluator | None = None,
        model_risk_service: ModelRiskRegisterService | None = None,
        event_log: Path = DEFAULT_EVENT_LOG,
        audit_log: Path = DEFAULT_AUDIT_LOG,
        metrics_path: Path = DEFAULT_METRICS_PATH,
    ) -> None:
        self._root = root
        self._config_path = config_path
        self._feature_flags_path = feature_flags_path
        self._roles_path = roles_path
        self._evidence_store = evidence_store or OpsEvidenceStore()
        self._ops_readiness = ops_readiness or OpsReadinessEvaluator()
        self._model_risk_service = model_risk_service or ModelRiskRegisterService()
        self._event_log = event_log
        self._audit_log = audit_log
        self._metrics_path = metrics_path

    def load_registry(self) -> list[IdeaRecord]:
        index_path = self._root / "index.yaml"
        if not index_path.exists():
            return []
        payload = _load_yaml(index_path)
        if not isinstance(payload, Mapping):
            return []
        records: list[IdeaRecord] = []
        for entry in payload.get("ideas") or []:
            if not isinstance(entry, Mapping):
                continue
            idea_id = str(entry.get("idea_id") or "").strip()
            if not idea_id:
                continue
            path = Path(entry.get("path") or (self._root / idea_id))
            records.append(
                IdeaRecord(
                    idea_id=idea_id,
                    title=str(entry.get("title") or ""),
                    owner=_optional_str(entry.get("owner")),
                    strategy_refs=_list_str(entry.get("strategy_refs")),
                    current_stage=str(entry.get("current_stage") or "draft"),
                    created_at=str(entry.get("created_at") or _utcnow_iso()),
                    tags=_list_str(entry.get("tags")),
                    path=path,
                )
            )
        return records

    def get_idea(self, idea_id: str) -> IdeaRecord:
        for record in self.load_registry():
            if record.idea_id == idea_id:
                return record
        raise IdeaNotFoundError(f"idea not found: {idea_id}")

    def evaluate_stage_transition(self, idea_id: str, target_stage: str) -> StageEvaluationResult:
        record = self.get_idea(idea_id)
        stage_def = self._stage_definition(target_stage)
        checklist = self._load_checklist(record, target_stage)
        reasons: list[str] = []
        actions: list[str] = []

        missing_items = checklist.missing_items()
        if missing_items:
            reasons.append("checklist_incomplete")
            actions.extend([f"checklist:{item.item_id}" for item in missing_items])

        evidence_issues = self._evaluate_evidence(record, stage_def.required_evidence)
        if evidence_issues:
            reasons.extend([f"evidence_missing:{issue}" for issue in evidence_issues])
            actions.extend([f"evidence:{issue}" for issue in evidence_issues])

        metrics_issues = self._evaluate_metrics(record, stage_def.minimum_metrics)
        if metrics_issues:
            reasons.extend([f"metrics_gap:{issue}" for issue in metrics_issues])
            actions.extend([f"metrics:{issue}" for issue in metrics_issues])

        weeks_in_stage = self._weeks_in_stage(record)
        if weeks_in_stage < stage_def.min_weeks_at_stage:
            reasons.append("insufficient_history")
            actions.append(
                f"min_weeks_at_stage:{stage_def.min_weeks_at_stage}"
            )

        if stage_def.feature_flags:
            missing_flags = [
                flag for flag in stage_def.feature_flags if not _feature_enabled(flag, self._feature_flags_path)
            ]
            if missing_flags:
                reasons.append("feature_disabled")
                actions.extend([f"feature:{flag}" for flag in missing_flags])

        ops_score = self._ops_readiness.evaluate().score
        if ops_score < OPS_READINESS_MIN_SCORE and target_stage in {"paper", "ready"}:
            reasons.append("ops_readiness_low")
            actions.append(f"ops_readiness:{ops_score:.1f}")

        if target_stage == "ready":
            model_risk_issues = self._evaluate_model_risk(record)
            if model_risk_issues:
                reasons.extend([f"model_risk:{issue}" for issue in model_risk_issues])
                actions.extend([f"model_risk:{issue}" for issue in model_risk_issues])

        allowed = not reasons
        return StageEvaluationResult(
            idea_id=idea_id,
            from_stage=record.current_stage,
            to_stage=target_stage,
            allowed=allowed,
            reasons=reasons,
            actions_required=actions,
        )

    def transition_stage(
        self,
        idea_id: str,
        target_stage: str,
        *,
        actor: str | None = None,
        note: str | None = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> StageEvaluationResult:
        record = self.get_idea(idea_id)
        evaluation = self.evaluate_stage_transition(idea_id, target_stage)
        if not evaluation.allowed and not force:
            return evaluation
        if force and not self._force_allowed(actor):
            evaluation.allowed = False
            evaluation.reasons.append("force_not_authorized")
            return evaluation
        if force and not evaluation.allowed:
            evaluation.allowed = True
            evaluation.reasons.append("force_override")
        if dry_run:
            return evaluation

        manifest = self._load_manifest(record)
        history = list(manifest.get("stage_history") or [])
        history.append(
            {
                "ts": _utcnow_iso(),
                "from": record.current_stage,
                "to": target_stage,
                "actor": actor,
                "note": note,
                "force": force,
            }
        )
        manifest["current_stage"] = target_stage
        manifest["stage_history"] = history
        self._write_manifest(record, manifest)
        self._update_index_stage(record.idea_id, target_stage)
        self._ensure_checklist(record, target_stage)

        self._append_jsonl(
            self._event_log,
            {
                "event": "ideas.stage_changed",
                "ts": _utcnow_iso(),
                "idea_id": idea_id,
                "from": record.current_stage,
                "to": target_stage,
                "actor": actor,
                "note": note,
                "force": force,
            },
        )
        self._append_jsonl(
            self._audit_log,
            {
                "event": "audit.idea_stage_transition",
                "ts": _utcnow_iso(),
                "idea_id": idea_id,
                "from": record.current_stage,
                "to": target_stage,
                "actor": actor,
                "note": note,
                "force": force,
            },
        )
        self._record_metrics(record, target_stage)
        return evaluation

    def record_checklist_progress(
        self,
        idea_id: str,
        *,
        stage: str,
        item_id: str,
        status: str,
        evidence_path: Path | None = None,
    ) -> ChecklistUpdateReceipt:
        record = self.get_idea(idea_id)
        checklist = self._load_checklist(record, stage)
        item = next((entry for entry in checklist.items if entry.item_id == item_id), None)
        if item is None:
            raise ChecklistIncompleteError(f"checklist item not found: {item_id}")
        item.status = status
        item.last_update_at = _utcnow_iso()
        if evidence_path is not None:
            item.evidence_path = str(evidence_path)
            self._register_evidence(record, stage, item, evidence_path)
        self._write_checklist(record, stage, checklist)
        payload = {
            "event": "audit.idea_checklist_updated",
            "ts": item.last_update_at,
            "idea_id": idea_id,
            "stage": stage,
            "item_id": item_id,
            "status": status,
            "evidence_path": item.evidence_path,
        }
        self._append_jsonl(self._audit_log, payload)
        self._record_metrics(record, record.current_stage)
        return ChecklistUpdateReceipt(
            idea_id=idea_id,
            stage=stage,
            item_id=item_id,
            status=status,
            evidence_path=item.evidence_path,
            updated_at=item.last_update_at,
        )

    def archive(self, idea_id: str, *, reason: str) -> ArchiveReceipt:
        record = self.get_idea(idea_id)
        manifest = self._load_manifest(record)
        manifest["current_stage"] = "archived"
        history = list(manifest.get("stage_history") or [])
        history.append(
            {
                "ts": _utcnow_iso(),
                "from": record.current_stage,
                "to": "archived",
                "actor": "system",
                "note": reason,
                "force": False,
            }
        )
        manifest["stage_history"] = history
        self._write_manifest(record, manifest)
        self._append_jsonl(
            self._audit_log,
            {
                "event": "audit.idea_archived",
                "ts": _utcnow_iso(),
                "idea_id": idea_id,
                "from": record.current_stage,
                "reason": reason,
            },
        )
        return ArchiveReceipt(
            idea_id=idea_id,
            previous_stage=record.current_stage,
            archived_at=_utcnow_iso(),
            reason=reason,
        )

    def summarize_pipeline(self) -> dict[str, object]:
        records = self.load_registry()
        by_stage: dict[str, int] = {}
        stalled: list[str] = []
        checklist_pending: list[str] = []
        for record in records:
            by_stage[record.current_stage] = by_stage.get(record.current_stage, 0) + 1
            if self._weeks_in_stage(record) >= 6:
                stalled.append(record.idea_id)
            checklist = self._load_checklist(record, record.current_stage)
            if checklist.missing_items():
                checklist_pending.append(record.idea_id)
        return {
            "total": len(records),
            "by_stage": by_stage,
            "stalled": stalled,
            "checklist_pending": checklist_pending,
        }

    def generate_pipeline_report(self, *, week: str, output_dir: Path) -> Path:
        summary = self.summarize_pipeline()
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"idea_pipeline_{week}.md"
        stage_lines = [f"- {stage}: {count}" for stage, count in sorted(summary["by_stage"].items())]
        stalled = summary["stalled"]
        stalled_block = "\n".join([f"- {idea_id}" for idea_id in stalled]) if stalled else "- n/a"
        pending = summary["checklist_pending"]
        pending_block = "\n".join([f"- {idea_id}" for idea_id in pending]) if pending else "- n/a"
        template_path = Path("src") / "reporter" / "templates" / "idea_pipeline_weekly.md"
        if template_path.exists():
            content = template_path.read_text(encoding="utf-8").format(
                week=week,
                total=summary["total"],
                stage_breakdown="\n".join(stage_lines) if stage_lines else "- n/a",
                stalled=stalled_block,
                checklist_pending=pending_block,
            )
            path.write_text(content, encoding="utf-8")
            return path
        lines = [
            f"# Idea Pipeline Report ({week})",
            "",
            f"- Total ideas: {summary['total']}",
            "",
            "## Stage Breakdown",
            *(stage_lines or ["- n/a"]),
            "",
            "## Stalled (>=6w)",
            stalled_block,
            "",
            "## Checklist Pending",
            pending_block,
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def _stage_definition(self, stage: str) -> StageDefinition:
        config = _load_yaml(self._config_path) if self._config_path.exists() else {}
        stages = config.get("stages") if isinstance(config, Mapping) else {}
        definition = stages.get(stage) if isinstance(stages, Mapping) else None
        if not isinstance(definition, Mapping):
            raise StageDefinitionMissing(f"stage not configured: {stage}")
        required_evidence = [
            EvidenceSpec(
                evidence_id=str(item.get("id")),
                path=str(item.get("path")),
                hash_required=bool(item.get("hash_required", False)),
                validation_playbook_id=_optional_str(item.get("validation_playbook_id")),
                expires_in_days=_optional_int(item.get("expires_in_days")),
            )
            for item in definition.get("required_evidence")
            or []
            if isinstance(item, Mapping)
        ]
        return StageDefinition(
            stage=stage,
            checklist_template=Path(str(definition.get("checklist_template"))),
            required_evidence=required_evidence,
            minimum_metrics={
                str(key): float(value)
                for key, value in (definition.get("minimum_metrics") or {}).items()
                if _is_number(value)
            },
            min_weeks_at_stage=int(definition.get("min_weeks_at_stage", 0)),
            feature_flags=[str(flag) for flag in definition.get("feature_flags") or []],
        )

    def get_stage_definition(self, stage: str) -> StageDefinition:
        return self._stage_definition(stage)

    def load_manifest(self, idea_id: str) -> dict[str, object]:
        record = self.get_idea(idea_id)
        return self._load_manifest(record)

    def load_checklist(self, idea_id: str, stage: str | None = None) -> StageChecklist:
        record = self.get_idea(idea_id)
        target_stage = stage or record.current_stage
        return self._load_checklist(record, target_stage)

    def _evaluate_evidence(
        self, record: IdeaRecord, specs: list[EvidenceSpec]
    ) -> list[str]:
        issues: list[str] = []
        for spec in specs:
            evidence_path = Path(spec.path)
            if not evidence_path.is_absolute():
                evidence_path = record.path / spec.path
            if not evidence_path.exists():
                issues.append(spec.evidence_id)
                continue
            if spec.hash_required:
                sha256_path(evidence_path)
        return issues

    def _evaluate_metrics(self, record: IdeaRecord, minimums: dict[str, float]) -> list[str]:
        if not minimums:
            return []
        manifest = self._load_manifest(record)
        metrics = manifest.get("metrics") or manifest.get("baseline_metrics") or {}
        issues: list[str] = []
        if not isinstance(metrics, Mapping):
            return list(minimums.keys())
        for key, bound in minimums.items():
            try:
                value = float(metrics.get(key))
            except (TypeError, ValueError):
                issues.append(key)
                continue
            if value < bound:
                issues.append(key)
        return issues

    def _evaluate_model_risk(self, record: IdeaRecord) -> list[str]:
        if not record.strategy_refs:
            return []
        try:
            register = self._model_risk_service.load(Path("docs/governance/model_risk_register.md"))
        except ModelRiskSchemaError:
            return ["register_unreadable"]
        issues = []
        for strategy_id in record.strategy_refs:
            entry = next(
                (item for item in register.entries if item.strategy_id == strategy_id), None
            )
            if entry is None:
                issues.append(f"missing:{strategy_id}")
            elif entry.status != "approved":
                issues.append(f"{strategy_id}:{entry.status}")
        return issues

    def _weeks_in_stage(self, record: IdeaRecord) -> int:
        manifest = self._load_manifest(record)
        history = manifest.get("stage_history")
        if not isinstance(history, list):
            return 0
        entries = [entry for entry in history if isinstance(entry, Mapping)]
        last_change = None
        for entry in reversed(entries):
            if entry.get("to") == record.current_stage:
                last_change = _parse_ts(entry.get("ts"))
                break
        if last_change is None:
            return 0
        delta = datetime.now(timezone.utc) - last_change
        return int(delta.days / 7)

    def _force_allowed(self, actor: str | None) -> bool:
        if actor is None:
            return False
        config = _load_yaml(self._config_path) if self._config_path.exists() else {}
        allow_roles = config.get("allow_force_roles") if isinstance(config, Mapping) else []
        if not allow_roles:
            return False
        role_map = _load_roles(self._roles_path)
        for role in allow_roles:
            members = role_map.get(role, [])
            if actor in members:
                return True
        return False

    def _load_manifest(self, record: IdeaRecord) -> dict[str, object]:
        manifest_path = record.path / "manifest.yaml"
        if not manifest_path.exists():
            return {"idea_id": record.idea_id, "current_stage": record.current_stage}
        payload = _load_yaml(manifest_path)
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _write_manifest(self, record: IdeaRecord, payload: Mapping[str, object]) -> None:
        record.path.mkdir(parents=True, exist_ok=True)
        manifest_path = record.path / "manifest.yaml"
        manifest_path.write_text(_dump_yaml(payload), encoding="utf-8")

    def _load_checklist(self, record: IdeaRecord, stage: str) -> StageChecklist:
        checklist_path = record.path / "checklists" / f"{stage}.yaml"
        if not checklist_path.exists():
            self._ensure_checklist(record, stage)
        payload = _load_yaml(checklist_path)
        if not isinstance(payload, Mapping):
            return StageChecklist(stage=stage)
        items: list[StageChecklistItem] = []
        for item in payload.get("items") or []:
            if not isinstance(item, Mapping):
                continue
            items.append(
                StageChecklistItem(
                    item_id=str(item.get("item_id") or ""),
                    description=str(item.get("description") or ""),
                    owner_role=_optional_str(item.get("owner_role")),
                    status=str(item.get("status") or "todo"),
                    evidence_path=_optional_str(item.get("evidence_path")),
                    last_update_at=_optional_str(item.get("last_update_at")),
                )
            )
        return StageChecklist(stage=str(payload.get("stage") or stage), items=items)

    def _ensure_checklist(self, record: IdeaRecord, stage: str) -> None:
        stage_def = self._stage_definition(stage)
        template_path = stage_def.checklist_template
        if not template_path.exists():
            return
        payload = _load_yaml(template_path)
        record.path.mkdir(parents=True, exist_ok=True)
        checklist_path = record.path / "checklists" / f"{stage}.yaml"
        checklist_path.parent.mkdir(parents=True, exist_ok=True)
        checklist_path.write_text(_dump_yaml(payload), encoding="utf-8")

    def _write_checklist(self, record: IdeaRecord, stage: str, checklist: StageChecklist) -> None:
        checklist_path = record.path / "checklists" / f"{stage}.yaml"
        checklist_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "stage": stage,
            "items": [item.to_dict() for item in checklist.items],
        }
        checklist_path.write_text(_dump_yaml(payload), encoding="utf-8")

    def _update_index_stage(self, idea_id: str, stage: str) -> None:
        index_path = self._root / "index.yaml"
        if not index_path.exists():
            return
        payload = _load_yaml(index_path)
        if not isinstance(payload, Mapping):
            return
        ideas = payload.get("ideas")
        if not isinstance(ideas, list):
            return
        updated = False
        for entry in ideas:
            if not isinstance(entry, Mapping):
                continue
            if str(entry.get("idea_id")) == idea_id:
                entry["current_stage"] = stage
                updated = True
                break
        if updated:
            index_path.write_text(_dump_yaml(payload), encoding="utf-8")

    def _register_evidence(
        self,
        record: IdeaRecord,
        stage: str,
        item: StageChecklistItem,
        evidence_path: Path,
    ) -> None:
        if not evidence_path.exists():
            raise EvidenceMissingError(f"evidence missing: {evidence_path}")
        self._evidence_store.register(
            category="idea_pipeline",
            artifact=evidence_path,
            runbook_refs=["GOV-IDEA-01"],
            validation_playbook_id=None,
            confidence_pct=0.95,
            expires_days=30,
            notes=f"idea={record.idea_id} stage={stage} item={item.item_id}",
        )

    def _record_metrics(self, record: IdeaRecord, stage: str) -> None:
        checklist = self._load_checklist(record, stage)
        payload = {
            "ts": _utcnow_iso(),
            "idea_id": record.idea_id,
            "stage": stage,
            "checklist_completion_pct": checklist.completion_pct(),
            "evidence_missing": len(checklist.missing_items()),
            "weeks_in_stage": self._weeks_in_stage(record),
        }
        self._append_jsonl(self._metrics_path, payload)

    @staticmethod
    def _append_jsonl(path: Path, payload: Mapping[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _load_yaml(path: Path) -> Mapping[str, Any] | list[Any] | str:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _dump_yaml(payload: Mapping[str, object]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        return dumper(dict(payload), sort_keys=False)
    return "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _list_str(value: object | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _is_number(value: object | None) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _feature_enabled(flag: str, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") if isinstance(payload, Mapping) else None
    if not isinstance(defaults, Mapping):
        return False
    profile = os.getenv("TRADECTL_PROFILE", "live")
    profile_defaults = defaults.get(profile)
    if not isinstance(profile_defaults, Mapping):
        return False
    return bool(profile_defaults.get(flag, False))


def _load_roles(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    roles = payload.get("roles") if isinstance(payload, Mapping) else {}
    if not isinstance(roles, Mapping):
        return {}
    mapping: dict[str, list[str]] = {}
    for role, detail in roles.items():
        if not isinstance(detail, Mapping):
            continue
        members = []
        for entry in detail.get("members") or []:
            if not isinstance(entry, Mapping):
                continue
            principal = entry.get("principal_id")
            if principal:
                members.append(str(principal))
        mapping[str(role)] = members
    return mapping


def _parse_ts(value: object | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


__all__ = [
    "IdeaPipelineManager",
    "IdeaPipelineError",
    "IdeaNotFoundError",
    "StageDefinitionMissing",
    "ChecklistIncompleteError",
    "EvidenceMissingError",
    "MetricsGapError",
    "IdeaRecord",
    "StageDefinition",
    "StageChecklist",
    "StageChecklistItem",
    "StageEvaluationResult",
]
