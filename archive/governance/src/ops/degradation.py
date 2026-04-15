"""Degradation playbook orchestration."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.ops.evidence import OpsEvidenceStore

DEFAULT_PLAYBOOK_DIR = Path("reports") / "ops" / "degradation_playbooks"
DEFAULT_EVENT_LOG = Path("logs") / "events" / "degradation_playbook.jsonl"
DEFAULT_SHADOW_EVENT_LOG = Path("logs") / "events" / "shadow_session.jsonl"
DEFAULT_AUDIT_LOG = Path("logs") / "audit" / "degradation_playbook.jsonl"
DEFAULT_METRICS_PATH = Path("metrics") / "degradation_playbook.jsonl"
DEFAULT_VALIDATION_PLAYBOOK = Path("docs") / "validation_playbook" / "AC34_degradation.yaml"
DEFAULT_EVIDENCE_LEDGER = Path("logs") / "audit" / "degradation_evidence.jsonl"
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")


class DegradationPlaybookError(RuntimeError):
    """Raised when degradation playbook operations fail."""


@dataclass(slots=True)
class ActionNode:
    node_id: str
    title: str
    owner: str
    runbook_ref: str
    status: str = "pending"
    evidence_required: bool = True
    depends_on: list[str] = field(default_factory=list)
    completed_at: str | None = None
    note: str | None = None
    evidence_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "owner": self.owner,
            "runbook_ref": self.runbook_ref,
            "status": self.status,
            "evidence_required": self.evidence_required,
            "depends_on": list(self.depends_on),
            "completed_at": self.completed_at,
            "note": self.note,
            "evidence_path": self.evidence_path,
        }


@dataclass(slots=True)
class PlaybookInstance:
    instance_id: str
    scenario_id: str
    severity: str
    status: str
    created_at: str
    updated_at: str
    nodes: list[ActionNode]
    reason: str | None = None
    recovery_report: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "degradation.playbook.v1",
            "instance_id": self.instance_id,
            "scenario_id": self.scenario_id,
            "severity": self.severity,
            "status": self.status,
            "reason": self.reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "nodes": [node.to_dict() for node in self.nodes],
            "recovery_report": self.recovery_report,
        }


class DegradationPlaybookOrchestrator:
    def __init__(
        self,
        *,
        playbook_dir: Path = DEFAULT_PLAYBOOK_DIR,
        event_log: Path = DEFAULT_EVENT_LOG,
        shadow_event_log: Path = DEFAULT_SHADOW_EVENT_LOG,
        audit_log: Path = DEFAULT_AUDIT_LOG,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        validation_playbook_path: Path = DEFAULT_VALIDATION_PLAYBOOK,
        evidence_ledger: Path = DEFAULT_EVIDENCE_LEDGER,
        ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
    ) -> None:
        self._playbook_dir = playbook_dir
        self._event_log = event_log
        self._shadow_event_log = shadow_event_log
        self._audit_log = audit_log
        self._metrics_path = metrics_path
        self._validation_playbook_path = validation_playbook_path
        self._evidence_store = OpsEvidenceStore(
            ledger_path=evidence_ledger,
            playbook_dir=validation_playbook_path.parent,
            ops_worklog_path=ops_worklog_path,
        )

    def start(
        self,
        scenario_id: str,
        *,
        severity: str,
        reason: str | None = None,
        dry_run: bool = False,
    ) -> PlaybookInstance:
        instance_id = _uuid7()
        now = _utcnow_iso()
        nodes = _load_scenario_nodes(scenario_id)
        if not nodes:
            raise DegradationPlaybookError(f"unknown scenario: {scenario_id}")
        instance = PlaybookInstance(
            instance_id=instance_id,
            scenario_id=scenario_id,
            severity=severity,
            status="dry_run" if dry_run else "in_progress",
            created_at=now,
            updated_at=now,
            nodes=nodes,
            reason=reason,
        )
        if not dry_run:
            self._persist(instance)
            self._append_event(
                self._event_log,
                {
                    "event": "degradation.playbook_started",
                    "ts": now,
                    "instance_id": instance_id,
                    "scenario_id": scenario_id,
                    "severity": severity,
                    "reason": reason,
                },
            )
            self._append_event(
                self._shadow_event_log,
                {
                    "event_type": "degradation.playbook_started",
                    "ts": now,
                    "instance_id": instance_id,
                    "scenario_id": scenario_id,
                    "severity": severity,
                },
            )
            self._append_audit(
                {
                    "event": "audit.degradation_playbook_started",
                    "ts": now,
                    "instance_id": instance_id,
                    "scenario_id": scenario_id,
                    "severity": severity,
                    "runbook_ref": nodes[0].runbook_ref if nodes else "n/a",
                }
            )
            self._append_metrics(instance)
        return instance

    def status(self, instance_id: str) -> PlaybookInstance:
        path = self._instance_path(instance_id)
        if not path.exists():
            raise DegradationPlaybookError(f"playbook instance not found: {instance_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _parse_instance(payload)

    def ack(
        self,
        instance_id: str,
        *,
        node_id: str,
        evidence_path: Path | None,
        actor: str | None,
        note: str | None = None,
        handoff: str | None = None,
    ) -> PlaybookInstance:
        instance = self.status(instance_id)
        node = _find_node(instance.nodes, node_id)
        if node.status == "completed":
            return instance
        if node.depends_on and not _deps_satisfied(instance.nodes, node.depends_on):
            raise DegradationPlaybookError("dependency_not_completed")
        if node.evidence_required and not evidence_path:
            raise DegradationPlaybookError("evidence_required")
        if evidence_path and not evidence_path.exists():
            raise DegradationPlaybookError("evidence_missing")
        now = _utcnow_iso()
        evidence_hash = None
        if evidence_path:
            evidence_hash = _hash_path(evidence_path)
            node.evidence_path = str(evidence_path)
            self._evidence_store.register(
                category="acceptable_degradation",
                artifact=evidence_path,
                runbook_refs=[node.runbook_ref] if node.runbook_ref else [],
                notes=note or "degradation playbook ack",
            )
        node.status = "completed"
        node.completed_at = now
        node.note = note
        instance.updated_at = now
        if _all_nodes_completed(instance.nodes):
            instance.status = "ready_for_recovery"
        self._persist(instance)
        self._append_event(
            self._event_log,
            {
                "event": "degradation.playbook_updated",
                "ts": now,
                "instance_id": instance_id,
                "node_id": node_id,
                "actor": actor,
                "handoff": handoff,
            },
        )
        self._append_event(
            self._shadow_event_log,
            {
                "event_type": "degradation.playbook_updated",
                "ts": now,
                "instance_id": instance_id,
                "node_id": node_id,
            },
        )
        self._append_audit(
            {
                "event": "audit.degradation_action_ack",
                "ts": now,
                "instance_id": instance_id,
                "node_id": node_id,
                "actor": actor,
                "evidence_hash": evidence_hash,
                "runbook_ref": node.runbook_ref,
            }
        )
        self._append_metrics(instance)
        return instance

    def recover(
        self,
        instance_id: str,
        *,
        attach_report: Path | None,
    ) -> PlaybookInstance:
        instance = self.status(instance_id)
        if not _all_nodes_completed(instance.nodes):
            raise DegradationPlaybookError("incomplete_nodes")
        if not attach_report:
            raise DegradationPlaybookError("recovery_report_required")
        if not attach_report.exists():
            raise DegradationPlaybookError("recovery_report_missing")
        now = _utcnow_iso()
        instance.status = "completed"
        instance.updated_at = now
        instance.recovery_report = str(attach_report)
        runbook_refs = []
        if instance.nodes:
            runbook_refs = [instance.nodes[0].runbook_ref] if instance.nodes[0].runbook_ref else []
        self._evidence_store.register(
            category="acceptable_degradation",
            artifact=attach_report,
            runbook_refs=runbook_refs,
            notes="degradation recovery report",
        )
        self._persist(instance)
        self._append_event(
            self._event_log,
            {
                "event": "degradation.playbook_completed",
                "ts": now,
                "instance_id": instance_id,
                "scenario_id": instance.scenario_id,
            },
        )
        self._append_event(
            self._shadow_event_log,
            {
                "event_type": "degradation.playbook_completed",
                "ts": now,
                "instance_id": instance_id,
                "scenario_id": instance.scenario_id,
            },
        )
        evidence_hash = _hash_path(attach_report)
        self._append_audit(
            {
                "event": "audit.degradation_recovered",
                "ts": now,
                "instance_id": instance_id,
                "scenario_id": instance.scenario_id,
                "runbook_ref": instance.nodes[0].runbook_ref if instance.nodes else "n/a",
                "evidence_hash": evidence_hash,
            }
        )
        self._append_validation_entry(instance, attach_report)
        self._append_metrics(instance)
        return instance

    def _append_validation_entry(
        self, instance: PlaybookInstance, attach_report: Path | None
    ) -> None:
        payload = {}
        path = self._validation_playbook_path
        if path.exists():
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            payload = {}
        if "validation_playbook_id" not in payload:
            payload["validation_playbook_id"] = path.stem
        if "category" not in payload:
            payload["category"] = "acceptable_degradation"
        entries = list(payload.get("entries") or [])
        entries.append(
            {
                "instance_id": instance.instance_id,
                "scenario_id": instance.scenario_id,
                "status": instance.status,
                "created_at": instance.created_at,
                "completed_at": instance.updated_at,
                "report_path": str(attach_report) if attach_report else None,
            }
        )
        payload["entries"] = entries
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump_yaml(payload), encoding="utf-8")

    def _append_metrics(self, instance: PlaybookInstance) -> None:
        completed = sum(1 for node in instance.nodes if node.status == "completed")
        payload = {
            "metric": "degradation_playbook",
            "ts": _utcnow_iso(),
            "instance_id": instance.instance_id,
            "scenario_id": instance.scenario_id,
            "severity": instance.severity,
            "status": instance.status,
            "node_completed": completed,
            "nodes_total": len(instance.nodes),
        }
        _append_event(self._metrics_path, payload)

    def _append_event(self, path: Path, payload: Mapping[str, object]) -> None:
        _append_event(path, payload)

    def _append_audit(self, payload: Mapping[str, object]) -> None:
        _append_event(self._audit_log, payload)

    def _persist(self, instance: PlaybookInstance) -> None:
        path = self._instance_path(instance.instance_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(instance.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _instance_path(self, instance_id: str) -> Path:
        return self._playbook_dir / f"{instance_id}.json"


def _load_scenario_nodes(scenario_id: str) -> list[ActionNode]:
    scenarios = {
        "data_latency": [
            ActionNode(
                node_id="notify_ops",
                title="Notify ops and review SLA metrics",
                owner="ops",
                runbook_ref="RUN-DATA-05",
                evidence_required=True,
            ),
            ActionNode(
                node_id="guarded_switch",
                title="Switch board to guarded mode",
                owner="ops",
                runbook_ref="RUN-DATA-05",
                evidence_required=True,
                depends_on=["notify_ops"],
            ),
            ActionNode(
                node_id="validate_recovery",
                title="Validate recovery metrics",
                owner="ops",
                runbook_ref="RUN-DATA-06",
                evidence_required=True,
                depends_on=["guarded_switch"],
            ),
        ],
        "rate_limit": [
            ActionNode(
                node_id="assess_rate_limit",
                title="Assess rate limit impact",
                owner="ops",
                runbook_ref="RUN-DATA-05",
                evidence_required=True,
            ),
            ActionNode(
                node_id="apply_fallback",
                title="Apply fallback provider",
                owner="ops",
                runbook_ref="RUN-DATA-06",
                evidence_required=True,
                depends_on=["assess_rate_limit"],
            ),
        ],
    }
    return [node for node in scenarios.get(scenario_id, [])]


def _find_node(nodes: list[ActionNode], node_id: str) -> ActionNode:
    for node in nodes:
        if node.node_id == node_id:
            return node
    raise DegradationPlaybookError(f"node not found: {node_id}")


def _deps_satisfied(nodes: list[ActionNode], deps: list[str]) -> bool:
    completed = {node.node_id for node in nodes if node.status == "completed"}
    return all(dep in completed for dep in deps)


def _all_nodes_completed(nodes: list[ActionNode]) -> bool:
    return all(node.status == "completed" for node in nodes)


def _parse_instance(payload: Mapping[str, Any]) -> PlaybookInstance:
    nodes = []
    for raw in payload.get("nodes") or []:
        nodes.append(
            ActionNode(
                node_id=str(raw.get("node_id") or ""),
                title=str(raw.get("title") or ""),
                owner=str(raw.get("owner") or ""),
                runbook_ref=str(raw.get("runbook_ref") or ""),
                status=str(raw.get("status") or "pending"),
                evidence_required=bool(raw.get("evidence_required", True)),
                depends_on=list(raw.get("depends_on") or []),
                completed_at=raw.get("completed_at"),
                note=raw.get("note"),
                evidence_path=raw.get("evidence_path"),
            )
        )
    return PlaybookInstance(
        instance_id=str(payload.get("instance_id") or ""),
        scenario_id=str(payload.get("scenario_id") or ""),
        severity=str(payload.get("severity") or "medium"),
        status=str(payload.get("status") or "unknown"),
        created_at=str(payload.get("created_at") or ""),
        updated_at=str(payload.get("updated_at") or ""),
        nodes=nodes,
        reason=payload.get("reason"),
        recovery_report=payload.get("recovery_report"),
    )


def _append_event(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), ensure_ascii=False) + "\n")


def _dump_yaml(payload: Mapping[str, object]) -> str:
    dumper = getattr(yaml, "safe_dump", None)
    if dumper:
        return dumper(dict(payload), sort_keys=False)
    return "# JSON\n" + json.dumps(payload, ensure_ascii=False, indent=2)


def _hash_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _uuid7() -> str:
    ts_ms = time.time_ns() // 1_000_000
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (ts_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b
    return str(uuid.UUID(int=value))


__all__ = [
    "ActionNode",
    "PlaybookInstance",
    "DegradationPlaybookOrchestrator",
    "DegradationPlaybookError",
]
