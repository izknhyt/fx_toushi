"""Onboarding checklist service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.core.health import HealthMonitor
from src.ops.evidence import OpsEvidenceStore

DEFAULT_ONBOARDING_PATH = Path("docs/onboarding.md")
DEFAULT_STATE_PATH = Path("reports/governance/onboarding_assignments.json")
DEFAULT_METRICS_PATH = Path("metrics/onboarding.jsonl")
DEFAULT_REPORT_DIR = Path("reports/governance/onboarding")


class OnboardingError(Exception):
    """Base exception for onboarding service failures."""


@dataclass(slots=True)
class OnboardingTask:
    slug: str
    title: str


class OnboardingChecklistService:
    def __init__(
        self,
        *,
        onboarding_path: Path = DEFAULT_ONBOARDING_PATH,
        state_path: Path = DEFAULT_STATE_PATH,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        report_dir: Path = DEFAULT_REPORT_DIR,
        evidence_store: OpsEvidenceStore | None = None,
    ) -> None:
        self._onboarding_path = onboarding_path
        self._state_path = state_path
        self._metrics_path = metrics_path
        self._report_dir = report_dir
        self._evidence_store = evidence_store or OpsEvidenceStore()

    def assign(self, *, user_id: str, mentor_id: str, dry_run: bool = False) -> dict[str, object]:
        tasks = self._load_tasks()
        state = self._load_state()
        assignment = state["assignments"].get(user_id, {})
        assignment.update(
            {
                "user_id": user_id,
                "mentor_id": mentor_id,
                "assigned_at": assignment.get("assigned_at") or _utcnow_iso(),
                "status": assignment.get("status") or "in_progress",
                "tasks": assignment.get("tasks")
                or [
                    {
                        "slug": task.slug,
                        "title": task.title,
                        "status": "not_started",
                        "completed_at": None,
                    }
                    for task in tasks
                ],
            }
        )
        state["assignments"][user_id] = assignment
        if not dry_run:
            self._write_state(state)
            self._append_metric(
                {
                    "metric": "onboarding_assigned",
                    "user_id": user_id,
                    "mentor_id": mentor_id,
                }
            )
        return {
            "status": "ok",
            "assignment": assignment,
            "dry_run": dry_run,
        }

    def complete(
        self,
        *,
        user_id: str,
        task_slug: str,
        dry_run: bool = False,
    ) -> dict[str, object]:
        state = self._load_state()
        assignment = state["assignments"].get(user_id)
        if not assignment:
            raise OnboardingError(f"assignment missing for {user_id}")
        updated = False
        for task in assignment.get("tasks", []):
            if task.get("slug") != task_slug:
                continue
            if task.get("status") != "complete":
                task["status"] = "complete"
                task["completed_at"] = _utcnow_iso()
                updated = True
        if not updated:
            raise OnboardingError(f"task not found: {task_slug}")
        completion_pct = _completion_pct(assignment.get("tasks", []))
        assignment["completion_pct"] = completion_pct
        if completion_pct >= 100:
            assignment["status"] = "complete"
            if not dry_run:
                evidence = self._render_report(assignment)
                self._append_validation_entry(
                    validation_id="AC16_onboarding",
                    evidence_path=evidence,
                    user_id=str(assignment.get("user_id") or ""),
                )
                self._evidence_store.register(
                    category="onboarding",
                    artifact=evidence,
                    validation_playbook_id=None,
                    confidence_pct=0.95,
                    notes=f"onboarding complete for {user_id}",
                )
        if not dry_run:
            self._write_state(state)
            self._append_metric(
                {
                    "metric": "onboarding_completion",
                    "user_id": user_id,
                    "completion_pct": completion_pct,
                }
            )
            self._check_lag(state)
        return {"status": "ok", "assignment": assignment, "dry_run": dry_run}

    def status(self) -> dict[str, object]:
        state = self._load_state()
        self._check_lag(state)
        return {"status": "ok", **state}

    def _load_tasks(self) -> list[OnboardingTask]:
        if not self._onboarding_path.exists():
            raise OnboardingError(f"onboarding path missing: {self._onboarding_path}")
        tasks: list[OnboardingTask] = []
        for line in self._onboarding_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line.startswith("- ["):
                continue
            title = line.split("]", 1)[-1].strip()
            if not title:
                continue
            tasks.append(OnboardingTask(slug=_slugify(title), title=title))
        if not tasks:
            raise OnboardingError("no onboarding tasks found")
        return tasks

    def _load_state(self) -> dict[str, object]:
        if not self._state_path.exists():
            return {"schema_version": "onboarding.v1", "assignments": {}}
        return json.loads(self._state_path.read_text(encoding="utf-8"))

    def _write_state(self, state: dict[str, object]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = _utcnow_iso()
        self._state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_metric(self, payload: dict[str, object]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": _utcnow_iso(), **payload}
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    def _render_report(self, assignment: dict[str, object]) -> Path:
        self._report_dir.mkdir(parents=True, exist_ok=True)
        user_id = assignment.get("user_id", "user")
        path = self._report_dir / f"onboarding_{user_id}.md"
        lines = [
            f"# Onboarding Completion: {user_id}",
            f"- mentor: {assignment.get('mentor_id')}",
            f"- assigned_at: {assignment.get('assigned_at')}",
            f"- completion_pct: {assignment.get('completion_pct')}",
            "",
            "## Tasks",
        ]
        for task in assignment.get("tasks", []):
            status = task.get("status")
            title = task.get("title")
            lines.append(f"- [{ 'x' if status == 'complete' else ' ' }] {title}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def _append_validation_entry(
        self, *, validation_id: str, evidence_path: Path, user_id: str
    ) -> None:
        path = Path("docs") / "validation_playbook" / f"{validation_id}.yaml"
        data = {}
        if path.exists():
            try:
                import yaml

                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        entries = list(data.get("entries") or [])
        entries.append(
            {
                "recorded_at": _utcnow_iso(),
                "user_id": user_id,
                "evidence_path": str(evidence_path),
            }
        )
        data["validation_playbook_id"] = validation_id
        data["category"] = data.get("category") or "onboarding"
        data["entries"] = entries
        path.write_text(_dump_yaml(data), encoding="utf-8")

    def _check_lag(self, state: dict[str, object]) -> None:
        now = datetime.now(timezone.utc)
        for assignment in state.get("assignments", {}).values():
            if assignment.get("status") == "complete":
                continue
            assigned_at = assignment.get("assigned_at")
            if not assigned_at:
                continue
            try:
                assigned_ts = datetime.fromisoformat(str(assigned_at).replace("Z", "+00:00"))
            except ValueError:
                continue
            lag_days = (now - assigned_ts).days
            if lag_days >= 90:
                HealthMonitor().raise_condition(
                    "info",
                    "onboarding_lag",
                    detail=f"user={assignment.get('user_id')}",
                )


def _completion_pct(tasks: list[dict[str, object]]) -> float:
    if not tasks:
        return 0.0
    completed = sum(1 for task in tasks if task.get("status") == "complete")
    return round(completed / len(tasks) * 100.0, 2)


def _slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_yaml(data: dict[str, object]) -> str:
    lines: list[str] = []
    if "validation_playbook_id" in data:
        lines.append(f"validation_playbook_id: {data['validation_playbook_id']}")
    if "category" in data:
        lines.append(f"category: {data['category']}")
    lines.append("entries:")
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        lines.append(f"  - recorded_at: {entry.get('recorded_at')}")
        lines.append(f"    user_id: {entry.get('user_id')}")
        lines.append(f"    evidence_path: {entry.get('evidence_path')}")
    return "\n".join(lines) + "\n"


__all__ = ["OnboardingChecklistService", "OnboardingError"]
