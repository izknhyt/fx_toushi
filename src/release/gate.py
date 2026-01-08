"""Minimal release gate service for M1.1 hardening."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Iterable, Mapping

from src.compliance import RiskDisclosureService

__all__ = ["ReleaseGateService", "ReleaseChecklist", "ReleaseTask"]


@dataclass(frozen=True)
class ReleaseTask:
    task_id: str
    label: str
    status: str
    evidence_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "label": self.label,
            "status": self.status,
            "evidence_path": self.evidence_path,
        }


@dataclass(frozen=True)
class ReleaseChecklist:
    version: str
    generated_at: str
    tasks: tuple[ReleaseTask, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "tasks": [task.to_dict() for task in self.tasks],
        }


class ReleaseGateService:
    """Track minimal release checklist progress."""

    def __init__(
        self,
        *,
        base_dir: Path = Path("reports/audit/release"),
        template_path: Path = Path("docs/release_checklist.md"),
        guardrails_metrics_path: Path = Path("metrics/guardrails.jsonl"),
    ) -> None:
        self._base_dir = base_dir
        self._template_path = template_path
        self._guardrails_metrics_path = guardrails_metrics_path

    def prepare(self, *, version: str) -> ReleaseChecklist:
        tasks = self._load_template_tasks() or self._default_tasks()
        checklist = ReleaseChecklist(
            version=version,
            generated_at=_utcnow_iso(),
            tasks=tuple(tasks),
        )
        self._base_dir.mkdir(parents=True, exist_ok=True)
        checklist_path = self._base_dir / f"{version}.md"
        state_path = self._base_dir / f"{version}.json"
        checklist_path.write_text(self._render_markdown(checklist), encoding="utf-8")
        state_path.write_text(json.dumps(checklist.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return checklist

    def record_result(
        self,
        *,
        version: str,
        task_id: str,
        status: str,
        evidence_path: str | None = None,
    ) -> ReleaseChecklist:
        checklist = self._load_state(version)
        updated: list[ReleaseTask] = []
        found = False
        for task in checklist.tasks:
            if task.task_id == task_id:
                updated.append(ReleaseTask(task_id=task.task_id, label=task.label, status=status, evidence_path=evidence_path))
                found = True
            else:
                updated.append(task)
        if not found:
            updated.append(ReleaseTask(task_id=task_id, label=task_id.replace("_", " "), status=status, evidence_path=evidence_path))
        next_state = ReleaseChecklist(version=version, generated_at=checklist.generated_at, tasks=tuple(updated))
        state_path = self._base_dir / f"{version}.json"
        state_path.write_text(json.dumps(next_state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        self._update_markdown(version=version, checklist=next_state)
        return next_state

    def verify_completion(self, *, version: str) -> Mapping[str, object]:
        checklist = self._load_state(version)
        pending = [task for task in checklist.tasks if task.status not in {"pass", "ok", "done"}]
        payload = {
            "status": "ok" if not pending else "blocked",
            "version": version,
            "pending": [task.to_dict() for task in pending],
        }
        if pending:
            self._emit_guardrails_block(reason="release_blocked")
        return payload

    def tag_release(self, *, version: str) -> Mapping[str, object]:
        result = self.verify_completion(version=version)
        if result.get("status") != "ok":
            return result
        tag_path = self._base_dir / f"{version}.tag"
        tag_path.write_text(_utcnow_iso(), encoding="utf-8")
        return {"status": "ok", "version": version, "tag_path": str(tag_path)}

    def _load_state(self, version: str) -> ReleaseChecklist:
        state_path = self._base_dir / f"{version}.json"
        if not state_path.exists():
            return self.prepare(version=version)
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        tasks = tuple(
            ReleaseTask(
                task_id=task.get("task_id", "unknown"),
                label=task.get("label", "unknown"),
                status=task.get("status", "pending"),
                evidence_path=task.get("evidence_path"),
            )
            for task in payload.get("tasks", [])
        )
        return ReleaseChecklist(
            version=str(payload.get("version", version)),
            generated_at=str(payload.get("generated_at", _utcnow_iso())),
            tasks=tasks,
        )

    def _update_markdown(self, *, version: str, checklist: ReleaseChecklist) -> None:
        checklist_path = self._base_dir / f"{version}.md"
        checklist_path.write_text(self._render_markdown(checklist), encoding="utf-8")

    def _render_markdown(self, checklist: ReleaseChecklist) -> str:
        lines = [f"# Release Checklist {checklist.version}", "", f"- generated_at: {checklist.generated_at}", ""]
        for task in checklist.tasks:
            mark = "x" if task.status in {"pass", "ok", "done"} else " "
            evidence = f" (evidence: {task.evidence_path})" if task.evidence_path else ""
            lines.append(f"- [{mark}] {task.label} [{task.task_id}] status={task.status}{evidence}")
        if self._template_path.exists():
            lines.extend(["", "---", "", self._template_path.read_text(encoding="utf-8")])
        return "\n".join(lines) + "\n"

    def _load_template_tasks(self) -> list[ReleaseTask]:
        if not self._template_path.exists():
            return []
        tasks: list[ReleaseTask] = []
        for line in self._template_path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^- \[[ xX]\] (.+)$", line.strip())
            if not match:
                continue
            label = match.group(1).strip()
            task_id = _slugify(label)
            tasks.append(ReleaseTask(task_id=task_id, label=label, status="pending"))
        return tasks

    @staticmethod
    def _default_tasks() -> list[ReleaseTask]:
        labels = [
            ("backtest_regression", "Backtest regression"),
            ("data_failover_drill", "Data failover drill evidence"),
            ("risk_disclosure_review", "Risk disclosure wording review"),
            ("runbook_update", "Runbook update check"),
        ]
        return [ReleaseTask(task_id=task_id, label=label, status="pending") for task_id, label in labels]

    def _emit_guardrails_block(self, *, reason: str) -> None:
        risk_state = RiskDisclosureService().fetch_state().status
        payload = {
            "timestamp": _utcnow_iso(),
            "health_state": "warn",
            "board_mode": "guarded",
            "kill_switch": "none",
            "spread_status": "normal",
            "reason": reason,
            "suggested_action": "release_checklist_incomplete",
            "reasons": [reason, "auto_execute_forced_off"],
            "exit_code": 62,
            "reduce_only": False,
            "ack_user": None,
            "risk_disclosure": risk_state,
            "profit_readiness_status": "guarded",
            "auto_execute": False,
            "auto_execute_forced_off": True,
        }
        self._guardrails_metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._guardrails_metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _slugify(text: str) -> str:
    lowered = text.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return cleaned or "task"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
