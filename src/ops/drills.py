"""Scaffolding for OpsDrillService as described in design §53.1."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from src.ops.automation import AutomationEffectDelta, AutomationEffectTracker
from src.ops.evidence import EvidenceError, OpsEvidenceStore
DRILL_SCENARIOS_CATALOG_PATH = Path("config/ops/drill_scenarios.yaml")
"""Canonical YAML catalog for registered drill scenarios."""

DRILL_PLANS_LOG_PATH = Path("logs/ops/drill_plan.jsonl")
"""JSONL log file storing scheduled drill plans."""

DRILL_EXECUTIONS_LOG_PATH = Path("logs/ops/drill_execution.jsonl")
"""JSONL log file capturing drill execution progress."""

DRILL_REPORT_TEMPLATE_PATH = Path("docs/templates/drill_report.md")
"""Template used for drill execution reports."""

DRILL_REPORT_DIR = Path("reports/drill")
"""Directory where drill reports are stored."""

DRILL_METRICS_PATH = Path("metrics/drill.jsonl")
"""Metrics log for drill step durations and outcomes."""

DRILL_EVENT_LOG_PATH = Path("logs/events/ops.drill.jsonl")
"""Event log for drill lifecycle events."""

RUNBOOK_DIR = Path("docs/runbooks")
"""Directory holding runbook markdown files."""

OPS_WORKLOG_PATH = Path("ops_worklog.jsonl")
"""Default location for ops worklog entries."""

OPS_DRILL_STARTED_EVENT = "ops.drill.started"
"""Event emitted when a drill execution transitions to ``running``."""

OPS_DRILL_COMPLETED_EVENT = "ops.drill.completed"
"""Event emitted when a drill execution is successfully completed."""

OPS_DRILL_ABORTED_EVENT = "ops.drill.aborted"
"""Event emitted when a drill execution is aborted prior to completion."""

OPS_AGENDA_DRILL_ADDED_EVENT = "ops.agenda.drill_added"
"""Event emitted when a drill plan is added to the Ops agenda."""


class DrillError(Exception):
    """Base exception for Ops drill orchestration."""


class DrillScenarioExistsError(DrillError):
    """Raised when attempting to register a duplicate drill scenario identifier."""


class DrillScenarioNotFoundError(DrillError):
    """Raised when a drill scenario cannot be located."""


class RunbookReferenceError(DrillError):
    """Raised when a drill references a Runbook entry that cannot be resolved."""


class DrillCapacityExceededError(DrillError):
    """Raised when scheduling a drill would exceed the concurrent execution capacity."""


class DrillPlanNotReadyError(DrillError):
    """Raised when attempting to start a drill plan that has not been approved."""


class DrillPreconditionError(DrillError):
    """Raised when Guarded/BoardMode requirements are not satisfied for the drill."""


class DrillStepValidationError(DrillError):
    """Raised when a recorded drill step fails validation."""


class DrillSignOffMissingError(DrillError):
    """Raised when completing a drill without the required sign-off entries."""


class DrillEvidenceError(DrillError):
    """Raised when drill evidence cannot be persisted."""


@dataclass(slots=True)
class SignOff:
    """Stakeholder acknowledgement captured for a drill outcome."""

    role: str
    actor: str
    status: str
    timestamp: datetime


@dataclass(slots=True)
class DrillScenario:
    """Definition of a drill scenario that can be scheduled and executed."""

    scenario_id: str
    title: str
    runbook_refs: list[str]
    validation_playbook_ids: list[str]
    trigger: str
    expected_duration_min: int
    impact_tags: set[str] = field(default_factory=set)


@dataclass(slots=True)
class DrillPlan:
    """Scheduled plan for executing a drill scenario."""

    plan_id: str
    scenario_id: str
    scheduled_for: datetime
    owner: str
    participants: list[str]
    board_mode_on_start: str
    acceptance_conditions: list[str]


@dataclass(slots=True)
class DrillExecution:
    """Runtime state of a drill plan during execution."""

    execution_id: str
    plan_id: str
    started_at: datetime | None
    ended_at: datetime | None
    status: str
    kill_switch_state: str
    board_mode: str
    notes: str | None = None


@dataclass(slots=True)
class DrillStep:
    """Single step recorded during a drill execution."""

    runbook_step: str
    duration_min: int
    comment: str | None = None
    evidence_paths: list[str] = field(default_factory=list)
    metrics: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class DrillOutcome:
    """Aggregated outcome data for a drill execution."""

    execution_id: str
    success: bool
    metrics: dict[str, object]
    follow_up_tickets: list[str]
    evidence_paths: list[str]
    sign_offs: list[SignOff]


class OpsDrillService:
    """Service responsible for drill scenario registration and orchestration."""

    # TODO(gpt-ops): When implementing drill completion, emit a report using
    # ``docs/templates/drill_report.md`` (see ``docs/templates/README.md`` for
    # usage guidance) so that Codex implementations can produce consistent
    # evidence packages.

    def __init__(
        self,
        *,
        scenarios_catalog: Path = DRILL_SCENARIOS_CATALOG_PATH,
        plans_log: Path = DRILL_PLANS_LOG_PATH,
        executions_log: Path = DRILL_EXECUTIONS_LOG_PATH,
        report_template: Path = DRILL_REPORT_TEMPLATE_PATH,
        report_dir: Path = DRILL_REPORT_DIR,
        metrics_path: Path = DRILL_METRICS_PATH,
        event_log_path: Path = DRILL_EVENT_LOG_PATH,
        runbook_dir: Path = RUNBOOK_DIR,
        ops_worklog_path: Path = OPS_WORKLOG_PATH,
        evidence_store: OpsEvidenceStore | None = None,
        automation_tracker: AutomationEffectTracker | None = None,
    ) -> None:
        """Create a drill service bound to the provided catalog and log locations."""

        self._scenarios_catalog = scenarios_catalog
        self._plans_log = plans_log
        self._executions_log = executions_log
        self._report_template = report_template
        self._report_dir = report_dir
        self._metrics_path = metrics_path
        self._event_log_path = event_log_path
        self._runbook_dir = runbook_dir
        self._ops_worklog_path = ops_worklog_path
        self._evidence_store = evidence_store or OpsEvidenceStore()
        self._automation_tracker = automation_tracker or AutomationEffectTracker()
        self._plans_log.parent.mkdir(parents=True, exist_ok=True)
        self._executions_log.parent.mkdir(parents=True, exist_ok=True)
        self._event_log_path.parent.mkdir(parents=True, exist_ok=True)

    def register_scenario(self, scenario: DrillScenario) -> DrillScenario:
        """Persist *scenario* to ``drill_scenarios.yaml`` and emit audit events."""

        catalog, scenarios = self._load_catalog()
        if scenario.scenario_id in scenarios:
            raise DrillScenarioExistsError(scenario.scenario_id)
        self._validate_runbook_refs(scenario.runbook_refs)
        scenarios[scenario.scenario_id] = {
            "title": scenario.title,
            "runbook_refs": list(scenario.runbook_refs),
            "validation_playbook_ids": list(scenario.validation_playbook_ids),
            "trigger": scenario.trigger,
            "expected_duration_min": scenario.expected_duration_min,
            "impact_tags": sorted(scenario.impact_tags),
        }
        catalog["scenarios"] = scenarios
        self._scenarios_catalog.parent.mkdir(parents=True, exist_ok=True)
        self._scenarios_catalog.write_text(
            _dump_catalog(catalog, scenarios), encoding="utf-8"
        )
        return scenario

    def schedule(self, plan: DrillPlan) -> DrillPlan:
        """Schedule *plan* into ``drill_plan.jsonl`` subject to capacity checks."""

        scenario = self._lookup_scenario(plan.scenario_id)
        if scenario is None:
            raise DrillScenarioNotFoundError(plan.scenario_id)
        record = {
            "plan_id": plan.plan_id,
            "scenario_id": plan.scenario_id,
            "scheduled_for": plan.scheduled_for.isoformat().replace("+00:00", "Z"),
            "owner": plan.owner,
            "participants": list(plan.participants),
            "board_mode_on_start": plan.board_mode_on_start,
            "acceptance_conditions": list(plan.acceptance_conditions),
        }
        with self._plans_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
        self._emit_event(
            OPS_DRILL_STARTED_EVENT.replace("started", "scheduled"),
            {
                "plan_id": plan.plan_id,
                "scenario_id": plan.scenario_id,
                "runbook_refs": scenario.runbook_refs,
                "validation_playbook_ids": scenario.validation_playbook_ids,
            },
        )
        self._emit_event(
            OPS_AGENDA_DRILL_ADDED_EVENT,
            {
                "plan_id": plan.plan_id,
                "scenario_id": plan.scenario_id,
                "scheduled_for": plan.scheduled_for.isoformat().replace("+00:00", "Z"),
                "board_mode": plan.board_mode_on_start,
            },
        )
        return plan

    def start(self, plan_id: str, *, actor: str) -> DrillExecution:
        """Transition the referenced plan to ``running`` and emit ``ops.drill.started``."""

        plan = self._lookup_plan(plan_id)
        if plan is None:
            raise DrillPlanNotReadyError(plan_id)
        execution_id = f"{plan_id}-run"
        execution = DrillExecution(
            execution_id=execution_id,
            plan_id=plan_id,
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            status="running",
            kill_switch_state="none",
            board_mode=plan.board_mode_on_start,
            notes=f"started_by={actor}",
        )
        self._append_execution(execution)
        self._emit_event(
            OPS_DRILL_STARTED_EVENT,
            {
                "execution_id": execution_id,
                "plan_id": plan_id,
                "actor": actor,
                "board_mode": execution.board_mode,
            },
        )
        self._append_worklog(
            {
                "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "task": "drill_start",
                "actor": actor,
                "plan_id": plan_id,
                "execution_id": execution_id,
                "board_mode": execution.board_mode,
            }
        )
        return execution

    def record_step(self, execution_id: str, step: DrillStep) -> None:
        """Record *step* progress, append to metrics logs, and update the worklog."""

        plan_id = _plan_id_from_execution_id(execution_id)
        scenario_id = None
        plan = self._lookup_plan(plan_id) if plan_id else None
        if plan:
            scenario_id = plan.scenario_id
        payload = {
            "execution_id": execution_id,
            "runbook_step": step.runbook_step,
            "duration_min": step.duration_min,
            "comment": step.comment,
            "evidence_paths": step.evidence_paths,
            "metrics": step.metrics,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        self._executions_log.parent.mkdir(parents=True, exist_ok=True)
        with self._executions_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
        self._append_jsonl(
            self._metrics_path,
            {
                "execution_id": execution_id,
                "scenario_id": scenario_id,
                "step": step.runbook_step,
                "duration_sec": int(step.duration_min * 60),
                "success": True,
            },
        )
        self._append_worklog(
            {
                "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "task": "drill_step",
                "execution_id": execution_id,
                "plan_id": plan_id,
                "step": step.runbook_step,
                "duration_min": step.duration_min,
            }
        )

    def complete(self, execution_id: str, outcome: DrillOutcome) -> DrillOutcome:
        """Finalize the drill execution and emit ``ops.drill.completed``."""

        plan_id = _plan_id_from_execution_id(execution_id)
        plan = self._lookup_plan(plan_id) if plan_id else None
        scenario = self._lookup_scenario(plan.scenario_id) if plan else None
        report_path = self._write_report(
            execution_id=execution_id,
            plan=plan,
            scenario=scenario,
            outcome=outcome,
        )
        if report_path is None:
            raise DrillEvidenceError("drill report template missing")
        validation_playbook_id = None
        if scenario and scenario.validation_playbook_ids:
            validation_playbook_id = scenario.validation_playbook_ids[0]
        if not validation_playbook_id:
            raise DrillEvidenceError("validation_playbook_id missing for drill evidence")
        try:
            evidence_entry = self._evidence_store.register(
                category="drill",
                artifact=report_path,
                runbook_refs=list(scenario.runbook_refs if scenario else []),
                validation_playbook_id=validation_playbook_id,
            )
        except EvidenceError as exc:
            raise DrillEvidenceError(str(exc)) from exc
        minutes_saved = (
            outcome.metrics.get("minutes_saved_estimate") if isinstance(outcome.metrics, dict) else None
        )
        if minutes_saved is not None:
            self._automation_tracker.apply(
                AutomationEffectDelta(
                    task="drill",
                    before_min=int(minutes_saved),
                    after_min=0,
                    runbook_ref=validation_playbook_id,
                    evidence=[str(report_path)],
                )
            )
        execution_state = self._lookup_execution_state(execution_id)
        payload = {
            "execution_id": execution_id,
            "status": "completed" if outcome.success else "failed",
            "metrics": outcome.metrics,
            "follow_up_tickets": outcome.follow_up_tickets,
            "evidence_paths": list(outcome.evidence_paths) + ([str(report_path)] if report_path else []),
            "evidence_entry": {
                "artifact": evidence_entry.artifact,
                "sha256": evidence_entry.sha256,
                "confidence_pct": evidence_entry.confidence_pct,
                "expires_at": evidence_entry.expires_at.isoformat().replace("+00:00", "Z")
                if evidence_entry.expires_at
                else None,
                "validation_playbook_id": evidence_entry.validation_playbook_id,
            },
            "sign_offs": [
                {
                    "role": s.role,
                    "actor": s.actor,
                    "status": s.status,
                    "timestamp": s.timestamp.isoformat().replace("+00:00", "Z"),
                }
                for s in outcome.sign_offs
            ],
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        with self._executions_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
        self._emit_event(
            OPS_DRILL_COMPLETED_EVENT,
            {
                "execution_id": execution_id,
                "plan_id": plan_id,
                "scenario_id": scenario.scenario_id if scenario else None,
                "success": outcome.success,
                "runbook_refs": scenario.runbook_refs if scenario else [],
                "validation_playbook_ids": scenario.validation_playbook_ids if scenario else [],
                "evidence_paths": payload["evidence_paths"],
            },
        )
        self._append_jsonl(
            self._metrics_path,
            {
                "execution_id": execution_id,
                "scenario_id": scenario.scenario_id if scenario else None,
                "success": outcome.success,
                "board_mode": execution_state.get("board_mode") if execution_state else None,
                "kill_switch_state": execution_state.get("kill_switch_state") if execution_state else None,
                "minutes_saved_estimate": outcome.metrics.get("minutes_saved_estimate")
                if isinstance(outcome.metrics, dict)
                else None,
            },
        )
        return outcome

    def abort(self, execution_id: str, *, reason: str, actor: str) -> DrillExecution:
        """Abort the running drill execution and emit ``ops.drill.aborted``."""

        execution = DrillExecution(
            execution_id=execution_id,
            plan_id=execution_id.split("-")[0],
            started_at=None,
            ended_at=datetime.now(timezone.utc),
            status="aborted",
            kill_switch_state="none",
            board_mode="guarded",
            notes=f"aborted_by={actor}; reason={reason}",
        )
        self._append_execution(execution)
        self._emit_event(
            OPS_DRILL_ABORTED_EVENT,
            {
                "execution_id": execution_id,
                "plan_id": execution.plan_id,
                "actor": actor,
                "reason": reason,
            },
        )
        return execution

    def list_scenarios(self) -> Iterable[DrillScenario]:
        """Iterate the registered drill scenarios from the catalog."""

        _, scenarios = self._load_catalog()
        result: list[DrillScenario] = []
        for scenario_id, data in scenarios.items():
            result.append(
                DrillScenario(
                    scenario_id=scenario_id,
                    title=data.get("title", ""),
                    runbook_refs=list(data.get("runbook_refs", [])),
                    validation_playbook_ids=list(data.get("validation_playbook_ids", [])),
                    trigger=data.get("trigger", ""),
                    expected_duration_min=int(data.get("expected_duration_min", 0)),
                    impact_tags=set(data.get("impact_tags", [])),
                )
            )
        return result

    def list_plans(self, *, include_completed: bool = False) -> Iterable[DrillPlan]:
        """Iterate scheduled drill plans optionally including completed ones."""

        if not self._plans_log.exists():
            return ()
        plans: list[DrillPlan] = []
        for line in self._plans_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                scheduled_for = datetime.fromisoformat(
                    str(data.get("scheduled_for")).replace("Z", "+00:00")
                )
            except Exception:
                continue
            plans.append(
                DrillPlan(
                    plan_id=str(data.get("plan_id", "")),
                    scenario_id=str(data.get("scenario_id", "")),
                    scheduled_for=scheduled_for,
                    owner=str(data.get("owner", "")),
                    participants=list(data.get("participants", [])),
                    board_mode_on_start=str(data.get("board_mode_on_start", "")),
                    acceptance_conditions=list(data.get("acceptance_conditions", [])),
                )
            )
        if include_completed:
            return plans
        return [p for p in plans if p.scheduled_for >= datetime.utcnow()]

    def _append_execution(self, execution: DrillExecution) -> None:
        payload = {
            "execution_id": execution.execution_id,
            "plan_id": execution.plan_id,
            "started_at": execution.started_at.isoformat().replace("+00:00", "Z")
            if execution.started_at
            else None,
            "ended_at": execution.ended_at.isoformat().replace("+00:00", "Z")
            if execution.ended_at
            else None,
            "status": execution.status,
            "kill_switch_state": execution.kill_switch_state,
            "board_mode": execution.board_mode,
            "notes": execution.notes,
        }
        with self._executions_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _lookup_execution_state(self, execution_id: str) -> dict[str, object] | None:
        if not self._executions_log.exists():
            return None
        lines = self._executions_log.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("execution_id") != execution_id:
                continue
            if "status" not in data and "board_mode" not in data:
                continue
            return data
        return None

    def _load_catalog(self) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
        catalog: dict[str, object] = {}
        if self._scenarios_catalog.exists():
            try:
                catalog = yaml.safe_load(self._scenarios_catalog.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                catalog = {}
        if not isinstance(catalog, dict):
            catalog = {}
        scenarios_raw = catalog.get("scenarios", {})
        scenarios: dict[str, dict[str, object]] = {}
        if isinstance(scenarios_raw, list):
            for entry in scenarios_raw:
                if not isinstance(entry, dict):
                    continue
                scenario_id = entry.get("scenario_id")
                if not scenario_id:
                    continue
                scenarios[str(scenario_id)] = dict(entry)
        elif isinstance(scenarios_raw, dict):
            scenarios = {str(key): dict(value) for key, value in scenarios_raw.items()}
        return catalog, scenarios

    def _lookup_plan(self, plan_id: str) -> DrillPlan | None:
        if not self._plans_log.exists():
            return None
        for line in self._plans_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("plan_id") != plan_id:
                continue
            try:
                scheduled_for = datetime.fromisoformat(
                    str(data.get("scheduled_for")).replace("Z", "+00:00")
                )
            except Exception:
                scheduled_for = datetime.now(timezone.utc)
            return DrillPlan(
                plan_id=str(data.get("plan_id", "")),
                scenario_id=str(data.get("scenario_id", "")),
                scheduled_for=scheduled_for,
                owner=str(data.get("owner", "")),
                participants=list(data.get("participants", [])),
                board_mode_on_start=str(data.get("board_mode_on_start", "normal")),
                acceptance_conditions=list(data.get("acceptance_conditions", [])),
            )
        return None

    def _lookup_scenario(self, scenario_id: str) -> DrillScenario | None:
        _, scenarios = self._load_catalog()
        data = scenarios.get(scenario_id)
        if not isinstance(data, dict):
            return None
        return DrillScenario(
            scenario_id=scenario_id,
            title=str(data.get("title", "")),
            runbook_refs=list(data.get("runbook_refs", [])),
            validation_playbook_ids=list(data.get("validation_playbook_ids", [])),
            trigger=str(data.get("trigger", "")),
            expected_duration_min=int(data.get("expected_duration_min", 0)),
            impact_tags=set(data.get("impact_tags") or []),
        )

    def _validate_runbook_refs(self, runbook_refs: Iterable[str]) -> None:
        missing: list[str] = []
        for ref in runbook_refs:
            runbook_id = str(ref).split("#", 1)[0]
            if not runbook_id:
                continue
            path = self._runbook_dir / f"{runbook_id}.md"
            if not path.exists():
                missing.append(runbook_id)
        if missing:
            raise RunbookReferenceError(", ".join(missing))

    def _write_report(
        self,
        *,
        execution_id: str,
        plan: DrillPlan | None,
        scenario: DrillScenario | None,
        outcome: DrillOutcome,
    ) -> Path | None:
        if not self._report_template.exists():
            return None
        self._report_dir.mkdir(parents=True, exist_ok=True)
        scenario_id = scenario.scenario_id if scenario else "unknown"
        report_path = self._report_dir / f"{_utc_today_jst()}_{scenario_id}.md"
        context = {
            "execution_id": execution_id,
            "scenario_id": scenario_id,
            "plan_id": plan.plan_id if plan else "unknown",
            "facilitator": plan.owner if plan and plan.owner else "n/a",
            "date_jst": _jst_date(),
            "runbook_refs": ", ".join(scenario.runbook_refs) if scenario else "n/a",
        }
        sections = {
            "timeline": outcome.metrics.get("timeline", []) if isinstance(outcome.metrics, dict) else [],
            "runbook_steps": outcome.metrics.get("runbook_steps", []) if isinstance(outcome.metrics, dict) else [],
            "sign_offs": [
                {
                    "role": s.role,
                    "name": s.actor,
                    "timestamp": s.timestamp.astimezone(timezone(timedelta(hours=9))).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "status": s.status,
                    "notes": "",
                }
                for s in outcome.sign_offs
            ],
            "follow_ups": outcome.metrics.get("follow_ups", []) if isinstance(outcome.metrics, dict) else [],
        }
        sla = outcome.metrics.get("sla", {}) if isinstance(outcome.metrics, dict) else {}
        rendered = _render_drill_template(
            self._report_template.read_text(encoding="utf-8"),
            context=context,
            sections=sections,
            sla=sla,
        )
        report_path.write_text(rendered, encoding="utf-8")
        return report_path

    def _emit_event(self, event: str, payload: dict[str, object]) -> None:
        record = {
            "event": event,
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            **payload,
        }
        self._append_jsonl(self._event_log_path, record)

    def _append_jsonl(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_worklog(self, payload: dict[str, object]) -> None:
        self._append_jsonl(self._ops_worklog_path, payload)


def _plan_id_from_execution_id(execution_id: str) -> str:
    if execution_id.endswith("-run"):
        return execution_id[:-4]
    return execution_id


def _utc_today_jst() -> str:
    now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
    return now.strftime("%Y%m%d")


def _jst_date() -> str:
    now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
    return now.strftime("%Y-%m-%d")


def _render_drill_template(
    template: str,
    *,
    context: dict[str, object],
    sections: dict[str, list[dict[str, object]]],
    sla: dict[str, object],
) -> str:
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    for field in ("target", "actual", "decision", "reason", "runbook_check"):
        rendered = rendered.replace(f"{{{{sla.{field}}}}}", str(sla.get(field, "n/a")))
    rendered = _render_section(rendered, "timeline", sections.get("timeline", []), ["ts", "actor", "event", "evidence"])
    rendered = _render_section(
        rendered,
        "runbook_steps",
        sections.get("runbook_steps", []),
        ["step_id", "expected", "actual", "notes"],
    )
    rendered = _render_section(
        rendered,
        "sign_offs",
        sections.get("sign_offs", []),
        ["role", "name", "timestamp", "status", "notes"],
    )
    rendered = _render_section(
        rendered,
        "follow_ups",
        sections.get("follow_ups", []),
        ["owner", "action", "ticket", "due_date", "status"],
    )
    return rendered


def _render_section(
    template: str,
    section: str,
    rows: list[dict[str, object]],
    columns: list[str],
) -> str:
    start_tag = f"{{#{section}}}"
    end_tag = f"{{/{section}}}"
    if start_tag not in template or end_tag not in template:
        return template
    start_index = template.index(start_tag)
    end_index = template.index(end_tag)
    row_template = template[start_index + len(start_tag) : end_index]
    if rows:
        rendered_rows = []
        for row in rows:
            line = row_template
            for col in columns:
                line = line.replace(f"{{{{{col}}}}}", str(row.get(col, "n/a")))
        rendered_rows.append(line)
        rendered_block = "".join(rendered_rows)
    else:
        line = row_template
        for col in columns:
            line = line.replace(f"{{{{{col}}}}}", "n/a")
        rendered_block = line
    return template[:start_index] + rendered_block + template[end_index + len(end_tag) :]


def _dump_catalog(
    catalog: dict[str, object],
    scenarios: dict[str, dict[str, object]],
) -> str:
    lines: list[str] = []
    for key in ("schema_version", "maintained_by", "last_reviewed_at"):
        if key in catalog:
            lines.append(f"{key}: {catalog[key]}")
    lines.append("scenarios:")
    for scenario_id, data in scenarios.items():
        lines.append(f"  - scenario_id: {scenario_id}")
        title = data.get("title", "")
        lines.append(f"    title: {title}")
        runbook_refs = data.get("runbook_refs", [])
        lines.append("    runbook_refs:")
        for ref in runbook_refs:
            lines.append(f"      - {ref}")
        validation_ids = data.get("validation_playbook_ids", [])
        lines.append("    validation_playbook_ids:")
        for ref in validation_ids:
            lines.append(f"      - {ref}")
        trigger = data.get("trigger", "")
        lines.append(f"    trigger: {trigger}")
        expected = data.get("expected_duration_min", 0)
        lines.append(f"    expected_duration_min: {expected}")
        impact_tags = data.get("impact_tags") or []
        lines.append("    impact_tags:")
        for tag in impact_tags:
            lines.append(f"      - {tag}")
    return "\n".join(lines) + "\n"
