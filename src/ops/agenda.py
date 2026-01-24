"""Scaffolding for OpsAgendaService as described in design §52.3."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from src.core.gate import GateState

DAILY_AGENDA_TEMPLATE_PATH = Path("docs/templates/daily_agenda.md")
"""Template used for generating daily Ops agenda documents."""

DAILY_AGENDA_OUTPUT_DIR = Path("docs/runbooks/daily_agenda")
"""Directory where generated agendas are stored."""

DRILL_PLANS_LOG_PATH = Path("logs/ops/drill_plan.jsonl")
"""JSONL log file storing scheduled drill plans."""

DRILL_EXECUTIONS_LOG_PATH = Path("logs/ops/drill_execution.jsonl")
"""JSONL log file capturing drill execution progress."""

DRILL_SCENARIOS_CATALOG_PATH = Path("config/ops/drill_scenarios.yaml")
"""Canonical YAML catalog for registered drill scenarios."""

OPS_WORKLOG_PATH = Path("ops_worklog.jsonl")
"""Default location for ops worklog entries."""

AUTOMATION_EFFECT_PATH = Path("automation_effect.jsonl")
"""Default ledger containing automation effect measurements."""

GATE_STATE_PATH = Path("snapshots/latest/gate_state.json")
"""Default GateState snapshot path."""

HEALTH_STATE_PATH = Path("snapshots/latest/health_state.json")
"""Default HealthState snapshot path."""

OPS_AGENDA_EVENT_LOG_PATH = Path("logs/events/ops.agenda.jsonl")
"""Event log for Ops agenda deferment events."""

OPS_AGENDA_METRICS_PATH = Path("metrics/ops_agenda.jsonl")
"""Metrics log for generated Ops agenda summaries."""

OPS_AGENDA_AUDIT_PATH = Path("logs/audit/ops_agenda_generated.jsonl")
"""Audit trail for Ops agenda generation."""
BROKER_ALERT_EVENT_LOG_PATH = Path("logs/events/broker_alerts.jsonl")
AUTONOMY_STAGE_EVENT_LOG_PATH = Path("logs/events/autonomy_stage.jsonl")

COACHING_INSIGHTS_LOG_PATH = Path("metrics/coaching_insights.jsonl")
"""Metrics log for coaching insight tasks."""

COMPLIANCE_REGRESSION_METRICS_PATH = Path("metrics/compliance_regression.json")
"""Latest compliance regression metrics snapshot."""

EXPERIMENT_TRACKER_EVENT_LOG_PATH = Path("logs/events/experiment_tracker.jsonl")
"""Experiment tracker event log for failed/mismatch runs."""

REGRESSION_BACKTEST_METRICS_PATH = Path("metrics/regression_backtest.jsonl")
"""Regression backtest summary metrics."""

ACCESS_REVIEW_REGISTRY_PATH = Path("reports/governance/access/reviews.jsonl")
"""Access review registry for governance review tasks."""

RUNBOOK_INVENTORY_PATH = Path("reports/governance/runbook_inventory_status.json")
"""Runbook review inventory exported by DocOps."""

VALIDATION_PLAYBOOK_DIR = Path("docs/validation_playbook")
"""Validation playbook directory containing AC entries."""

OPS_AGENDA_GENERATED_EVENT = "ops.agenda.generated"
"""Event emitted after a new Ops agenda has been written to disk."""

OPS_AGENDA_DEFERRED_EVENT = "ops.agenda.deferred"
"""Event emitted when a drill or task must be rescheduled."""


class AgendaError(Exception):
    """Base exception for Ops agenda generation."""


class AgendaAlreadyExistsError(AgendaError):
    """Raised when attempting to generate an agenda that already exists without force."""


@dataclass(slots=True)
class AgendaContext:
    """Aggregated context used to render the Ops agenda template."""

    target_date: date
    health_state: str
    board_mode: str
    workload_total_min: int
    automation_gain_min: int
    critical_first: list[dict[str, object]]
    operational_tasks: list[dict[str, object]]
    runbook_reviews: list[dict[str, object]]
    validation_pending: list[dict[str, object]]
    drill_pending: list[dict[str, object]]
    deferred_drills: list[dict[str, object]]


class OpsAgendaService:
    """Service responsible for composing and writing Ops agendas."""

    def __init__(
        self,
        *,
        template_path: Path = DAILY_AGENDA_TEMPLATE_PATH,
        output_dir: Path = DAILY_AGENDA_OUTPUT_DIR,
        drill_plans_log: Path = DRILL_PLANS_LOG_PATH,
        drill_executions_log: Path = DRILL_EXECUTIONS_LOG_PATH,
        scenarios_catalog: Path = DRILL_SCENARIOS_CATALOG_PATH,
        ops_worklog_path: Path = OPS_WORKLOG_PATH,
        automation_effect_path: Path = AUTOMATION_EFFECT_PATH,
        gate_state_path: Path = GATE_STATE_PATH,
        health_state_path: Path = HEALTH_STATE_PATH,
        runbook_inventory_path: Path = RUNBOOK_INVENTORY_PATH,
        validation_playbook_dir: Path = VALIDATION_PLAYBOOK_DIR,
        access_review_registry_path: Path = ACCESS_REVIEW_REGISTRY_PATH,
        event_log_path: Path = OPS_AGENDA_EVENT_LOG_PATH,
        metrics_path: Path = OPS_AGENDA_METRICS_PATH,
        audit_path: Path = OPS_AGENDA_AUDIT_PATH,
    ) -> None:
        """Create a new agenda service bound to the given template and output directory."""

        self._template_path = template_path
        self._output_dir = output_dir
        self._drill_plans_log = drill_plans_log
        self._drill_executions_log = drill_executions_log
        self._scenarios_catalog = scenarios_catalog
        self._ops_worklog_path = ops_worklog_path
        self._automation_effect_path = automation_effect_path
        self._gate_state_path = gate_state_path
        self._health_state_path = health_state_path
        self._runbook_inventory_path = runbook_inventory_path
        self._validation_playbook_dir = validation_playbook_dir
        self._access_review_registry_path = access_review_registry_path
        self._event_log_path = event_log_path
        self._metrics_path = metrics_path
        self._audit_path = audit_path

    def generate(self, *, target_date: date, force: bool = False) -> Path:
        """Generate an agenda for *target_date* and return the resulting Markdown path."""

        rendered, ctx = self.render(target_date=target_date)
        output_path = self._output_dir / f"{ctx.target_date}.md"
        if output_path.exists() and not force:
            raise AgendaAlreadyExistsError(str(output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        self._append_metrics(ctx)
        self._append_audit(output_path, rendered)
        return output_path

    def render(self, *, target_date: date) -> tuple[str, AgendaContext]:
        """Render the agenda content without persisting to disk."""

        if not self._template_path.exists():
            raise FileNotFoundError(self._template_path)
        content = self._template_path.read_text(encoding="utf-8")
        ctx = self.build_context(target_date=target_date)
        return _render_agenda_template(content, ctx), ctx

    def build_context(self, *, target_date: date) -> AgendaContext:
        """Collect inputs and compute the :class:`AgendaContext` for *target_date*."""

        board_mode = _resolve_board_mode(self._gate_state_path)
        health_snapshot = _load_health_state(self._health_state_path)
        drill_pending, deferred = self._collect_pending_drills(target_date, board_mode=board_mode)
        workload_total_min = _sum_worklog_minutes(
            self._ops_worklog_path, target_date - timedelta(days=1)
        )
        automation_gain_min = _sum_automation_gain(
            self._automation_effect_path, target_date - timedelta(days=1)
        )
        runbook_reviews = _collect_runbook_reviews(self._runbook_inventory_path)
        validation_pending = _collect_validation_pending(self._validation_playbook_dir)
        critical_first = _build_critical_first(
            health_snapshot,
            self._ops_worklog_path,
            target_date=target_date,
        )
        idea_tasks = _collect_idea_pipeline_tasks(target_date=target_date)
        coaching_tasks = _collect_coaching_tasks(
            target_date=target_date,
            insights_log=COACHING_INSIGHTS_LOG_PATH,
        )
        compliance_tasks = _collect_compliance_regression_tasks(
            target_date=target_date,
            metrics_path=COMPLIANCE_REGRESSION_METRICS_PATH,
        )
        regression_tasks = _collect_regression_backtest_tasks(
            target_date=target_date,
            metrics_path=REGRESSION_BACKTEST_METRICS_PATH,
        )
        access_review_tasks = _collect_access_review_tasks(
            target_date=target_date,
            reviews_path=self._access_review_registry_path,
        )
        experiment_tasks = _collect_experiment_tracker_tasks(
            target_date=target_date,
            event_log=EXPERIMENT_TRACKER_EVENT_LOG_PATH,
        )
        broker_monitor_tasks = _collect_broker_monitor_tasks(
            target_date=target_date, alert_log=BROKER_ALERT_EVENT_LOG_PATH
        )
        autonomy_stage_tasks = _collect_autonomy_stage_tasks(
            target_date=target_date, event_log=AUTONOMY_STAGE_EVENT_LOG_PATH
        )
        agenda_events = _collect_ops_agenda_events(
            target_date=target_date, event_log=self._event_log_path
        )
        return AgendaContext(
            target_date=target_date,
            health_state=health_snapshot["status"],
            board_mode=board_mode,
            workload_total_min=workload_total_min,
            automation_gain_min=automation_gain_min,
            critical_first=critical_first,
            operational_tasks=(
                idea_tasks
                + coaching_tasks
                + compliance_tasks
                + regression_tasks
                + access_review_tasks
                + experiment_tasks
                + broker_monitor_tasks
                + autonomy_stage_tasks
                + agenda_events
            ),
            runbook_reviews=runbook_reviews,
            validation_pending=validation_pending,
            drill_pending=drill_pending,
            deferred_drills=deferred,
        )

    def _collect_pending_drills(
        self, target_date: date, *, board_mode: str
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        scenarios = _load_scenarios(self._scenarios_catalog)
        completion = _load_drill_completion(self._drill_executions_log)
        pending: list[dict[str, object]] = []
        deferred: list[dict[str, object]] = []
        for plan in _load_drill_plans(self._drill_plans_log):
            scenario = scenarios.get(plan["scenario_id"], {})
            scheduled_for = plan["scheduled_for"]
            if scheduled_for.date() > target_date:
                continue
            plan_id = plan["plan_id"]
            if completion.get(plan_id) in {"completed", "failed", "aborted"}:
                continue
            entry = {
                "plan_id": plan_id,
                "scenario_id": plan["scenario_id"],
                "scheduled_for": scheduled_for.isoformat().replace("+00:00", "Z"),
                "owner": plan.get("owner") or "n/a",
                "impact_tags": ", ".join(sorted(scenario.get("impact_tags") or [])) or "n/a",
                "board_mode": plan.get("board_mode_on_start", "guarded"),
            }
            impact_tags = set(scenario.get("impact_tags") or [])
            if board_mode != "normal" and "critical" not in impact_tags:
                deferred.append(entry)
                self._emit_event(
                    OPS_AGENDA_DEFERRED_EVENT,
                    {
                        "plan_id": plan_id,
                        "scenario_id": plan["scenario_id"],
                        "reason": "board_mode_guarded",
                    },
                )
                continue
            pending.append(entry)
        return pending, deferred

    def _emit_event(self, event: str, payload: dict[str, object]) -> None:
        record = {
            "event": event,
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            **payload,
        }
        self._event_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._event_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    def _append_metrics(self, ctx: AgendaContext) -> None:
        payload = {
            "date": str(ctx.target_date),
            "critical_tasks": len(ctx.critical_first),
            "pending_validation": len(ctx.validation_pending),
            "pending_runbooks": len(ctx.runbook_reviews),
            "health_state": ctx.health_state,
            "board_mode": ctx.board_mode,
        }
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_audit(self, output_path: Path, rendered: str) -> None:
        payload = {
            "event": OPS_AGENDA_GENERATED_EVENT,
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "path": str(output_path),
            "entry_hash": _hash_text(rendered),
            "approver": None,
            "evidence": str(output_path),
        }
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _render_agenda_template(template: str, ctx: AgendaContext) -> str:
    rendered = template
    agenda_map = {
        "date": str(ctx.target_date),
        "date_cli": str(ctx.target_date),
        "health_state": ctx.health_state,
        "board_mode": ctx.board_mode,
        "kill_switch_state": "none",
        "workload_total_min": str(_safe_int(ctx.workload_total_min)),
        "automation_gain_min": str(_safe_int(ctx.automation_gain_min)),
        "duration_min": str(_safe_int(0)),
    }
    health_reasons = ", ".join(
        [str(item.get("description")) for item in ctx.critical_first[:3]]
    ) or "n/a"
    summary_map = {
        "worklog_snapshot": f"{_safe_int(ctx.workload_total_min)} min",
        "health_reasons": health_reasons,
        "validation_pending": str(len(ctx.validation_pending)) if ctx.validation_pending else "0",
        "deadlines": str(len(ctx.runbook_reviews)) if ctx.runbook_reviews else "0",
        "notes": "n/a",
    }
    for key, value in agenda_map.items():
        rendered = rendered.replace(f"{{{{agenda.{key}}}}}", str(value))
    for key, value in summary_map.items():
        rendered = rendered.replace(f"{{{{summary.{key}}}}}", str(value))
    rendered = _render_critical_items(rendered, ctx.critical_first)
    rendered = _render_section(
        rendered,
        "operational.tasks",
        ctx.operational_tasks,
        ["task", "owner", "due", "estimate_min", "last_worklog", "notes"],
    )
    rendered = _render_section(
        rendered,
        "runbook_reviews",
        ctx.runbook_reviews,
        ["runbook_id", "status", "review_due_in_days", "owner", "follow_up"],
    )
    rendered = _render_section(
        rendered,
        "validation_pending",
        ctx.validation_pending,
        ["playbook_id", "artifact", "owner", "due", "evidence"],
    )
    rendered = _render_section(
        rendered,
        "drill_pending",
        ctx.drill_pending,
        ["plan_id", "scenario_id", "scheduled_for", "owner", "impact_tags", "board_mode"],
    )
    return rendered


def _render_critical_items(template: str, items: list[dict[str, object]]) -> str:
    rendered = template
    defaults = [
        {"description": "n/a", "owner": "n/a", "due": "n/a", "runbook_ref": "n/a"}
        for _ in range(3)
    ]
    for index in range(3):
        entry = defaults[index]
        if index < len(items) and isinstance(items[index], dict):
            entry = items[index]  # type: ignore[assignment]
        for field, value in entry.items():
            rendered = rendered.replace(
                f"{{{{critical.items[{index}].{field}}}}}",
                str(value),
            )
    return rendered


def _render_section(
    template: str,
    section: str,
    rows: list[dict[str, object]] | list[str],
    columns: list[str],
) -> str:
    start_tag = f"{{#{section}}}"
    end_tag = f"{{/{section}}}"
    if start_tag not in template or end_tag not in template:
        return template
    start_index = template.index(start_tag)
    end_index = template.index(end_tag)
    row_template = template[start_index + len(start_tag) : end_index]
    rendered_rows: list[str] = []
    if rows:
        for row in rows:
            entry = row if isinstance(row, dict) else {"value": row}
            line = row_template
            for col in columns:
                line = line.replace(f"{{{{{col}}}}}", str(entry.get(col, "n/a")))
            rendered_rows.append(line)
    else:
        line = row_template
        for col in columns:
            line = line.replace(f"{{{{{col}}}}}", "n/a")
        rendered_rows.append(line)
    rendered_block = "".join(rendered_rows)
    return template[:start_index] + rendered_block + template[end_index + len(end_tag) :]


def _safe_int(value: int) -> int:
    return int(value) if value is not None else 0


def _resolve_board_mode(gate_state_path: Path) -> str:
    if not gate_state_path.exists():
        return "normal"
    try:
        state = GateState.load(gate_state_path)
    except Exception:
        return "normal"
    return "normal" if state.auto_execute else "guarded"


def _load_scenarios(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    scenarios_raw = payload.get("scenarios", {})
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
    return scenarios


def _load_drill_plans(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    plans: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        scheduled_for = _parse_ts(data.get("scheduled_for")) or datetime.now(timezone.utc)
        plans.append(
            {
                "plan_id": str(data.get("plan_id", "")),
                "scenario_id": str(data.get("scenario_id", "")),
                "scheduled_for": scheduled_for,
                "owner": data.get("owner"),
                "board_mode_on_start": data.get("board_mode_on_start", "guarded"),
            }
        )
    return plans


def _load_drill_completion(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    completion: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        execution_id = data.get("execution_id")
        if not execution_id:
            continue
        status = data.get("status")
        if not status:
            continue
        plan_id = data.get("plan_id") or _plan_id_from_execution_id(str(execution_id))
        completion[str(plan_id)] = str(status)
    return completion


def _plan_id_from_execution_id(execution_id: str) -> str:
    if execution_id.endswith("-run"):
        return execution_id[:-4]
    return execution_id


def _sum_worklog_minutes(path: Path, target_date: date) -> int:
    if not path.exists():
        return 0
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_ts(data.get("ts"))
        if not ts or ts.date() != target_date:
            continue
        try:
            total += int(data.get("duration_min", 0))
        except (TypeError, ValueError):
            continue
    return total


def _sum_automation_gain(path: Path, target_date: date) -> int:
    if not path.exists():
        return 0
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        effective_date = data.get("effective_date")
        if str(effective_date) != str(target_date):
            continue
        try:
            total += int(data.get("gain_min", 0))
        except (TypeError, ValueError):
            continue
    return total


def _parse_ts(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _load_health_state(path: Path = HEALTH_STATE_PATH) -> dict[str, object]:
    if not path.exists():
        return {"status": "ok", "reasons": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "unknown", "reasons": []}
    status = payload.get("status") or "unknown"
    reasons = payload.get("reasons") or []
    return {"status": status, "reasons": reasons}


def _build_critical_first(
    health_snapshot: dict[str, object],
    worklog_path: Path,
    *,
    target_date: date,
) -> list[dict[str, object]]:
    status = str(health_snapshot.get("status") or "ok")
    reasons = health_snapshot.get("reasons") or []
    if status == "ok" and not reasons:
        return []
    completed_codes = _load_completed_health_codes(
        worklog_path, days=7, reference_date=target_date
    )
    items: list[dict[str, object]] = []
    for reason in reasons:
        if not isinstance(reason, dict):
            continue
        code = str(reason.get("code") or "unknown")
        task_id = f"health.{code}"
        if code in completed_codes or task_id in completed_codes:
            continue
        recommended_action = str(reason.get("recommended_action") or "")
        runbook_ref = _extract_runbook_ref(recommended_action)
        description = code
        detail = reason.get("detail")
        if detail:
            description = f"{code} ({detail})"
        items.append(
            {
                "task_id": task_id,
                "description": description,
                "owner": "ops",
                "due": str(target_date),
                "runbook_ref": runbook_ref or "n/a",
            }
        )
    return items


def _load_completed_health_codes(
    path: Path, *, days: int, reference_date: date | None = None
) -> set[str]:
    if not path.exists():
        return set()
    if reference_date is None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    else:
        cutoff = datetime.combine(reference_date, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
            days=days
        )
    codes: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _parse_ts(data.get("ts"))
        if not ts or ts < cutoff:
            continue
        task = data.get("task")
        if task:
            task_value = str(task)
            if task_value.startswith("health."):
                codes.add(task_value.replace("health.", "", 1))
            codes.add(task_value)
        if data.get("task") == "degraded_ack.registered":
            reason = data.get("reason") or data.get("notes") or ""
            for token in _split_reason_tokens(str(reason)):
                codes.add(token)
    return codes


def _split_reason_tokens(reason: str) -> list[str]:
    if not reason:
        return []
    normalized = reason.replace(",", " ").replace(";", " ")
    tokens = [token.strip() for token in normalized.split() if token.strip()]
    return tokens


def _extract_runbook_ref(recommended_action: str) -> str | None:
    if not recommended_action:
        return None
    if "runbook:" in recommended_action:
        return recommended_action.split("runbook:", 1)[1].strip()
    return None


def _collect_runbook_reviews(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    runbooks = payload.get("runbooks") or {}
    reviews: list[dict[str, object]] = []
    if isinstance(runbooks, dict):
        for runbook_id, entry in runbooks.items():
            if not isinstance(entry, dict):
                continue
            review_due_in_days = entry.get("review_due_in_days")
            status = entry.get("status") or "unknown"
            if review_due_in_days is None:
                continue
            try:
                review_due_in_days = int(review_due_in_days)
            except (TypeError, ValueError):
                continue
            if review_due_in_days <= 0 or status not in {"ready", "ok"}:
                reviews.append(
                    {
                        "runbook_id": str(runbook_id),
                        "status": str(status),
                        "review_due_in_days": review_due_in_days,
                        "owner": entry.get("doc_owner") or "n/a",
                        "follow_up": "review_due" if review_due_in_days <= 0 else "status_check",
                    }
                )
    return reviews


def _collect_validation_pending(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    pending: list[dict[str, object]] = []
    for playbook_path in sorted(path.glob("*.yaml")):
        try:
            payload = yaml.safe_load(playbook_path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        entries = payload.get("entries")
        if entries:
            continue
        playbook_id = payload.get("validation_playbook_id") or playbook_path.stem
        pending.append(
            {
                "playbook_id": str(playbook_id),
                "artifact": str(playbook_path),
                "owner": "ops",
                "due": "asap",
                "evidence": "add entry",
            }
        )
    return pending


def _collect_idea_pipeline_tasks(target_date: date) -> list[dict[str, object]]:
    if not _idea_pipeline_enabled():
        return []
    from src.ideas.manager import IdeaPipelineManager

    manager = IdeaPipelineManager()
    summary = manager.summarize_pipeline()
    tasks: list[dict[str, object]] = []
    for idea_id in summary.get("stalled", []):
        tasks.append(
            {
                "task": f"Review stalled idea {idea_id}",
                "owner": "research",
                "due": str(target_date),
                "estimate_min": 45,
                "last_worklog": "n/a",
                "notes": "Idea pipeline stalled >=6w",
            }
        )
    for idea_id in summary.get("checklist_pending", []):
        tasks.append(
            {
                "task": f"Complete checklist for {idea_id}",
                "owner": "research",
                "due": str(target_date),
                "estimate_min": 30,
                "last_worklog": "n/a",
                "notes": "Checklist incomplete",
            }
        )
    return tasks


def _collect_coaching_tasks(
    *, target_date: date, insights_log: Path = COACHING_INSIGHTS_LOG_PATH
) -> list[dict[str, object]]:
    if not insights_log.exists():
        return []
    tasks: list[dict[str, object]] = []
    for line in insights_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("status") != "over_threshold":
            continue
        due = record.get("due_date") or str(target_date)
        tasks.append(
            {
                "task": f"Coaching: {record.get('bottleneck_metric')}",
                "owner": "ops",
                "due": due,
                "estimate_min": 60,
                "last_worklog": record.get("insight_id", "n/a"),
                "notes": record.get("recommendation") or "Review coaching insight",
            }
        )
    return tasks


def _collect_compliance_regression_tasks(
    *, target_date: date, metrics_path: Path = COMPLIANCE_REGRESSION_METRICS_PATH
) -> list[dict[str, object]]:
    if not metrics_path.exists():
        return []
    try:
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    violations = int(payload.get("min_distance_violations", 0)) + int(
        payload.get("freeze_level_violations", 0)
    )
    drop_pct = float(payload.get("proposal_drop_pct", 1.0) or 1.0)
    if violations == 0 and drop_pct >= 0.5:
        return []
    return [
        {
            "task": "Review compliance regression results",
            "owner": "compliance",
            "due": str(target_date),
            "estimate_min": 45,
            "last_worklog": payload.get("generated_at", "n/a"),
            "notes": f"violations={violations}, drop_pct={drop_pct}",
        }
    ]


def _collect_experiment_tracker_tasks(
    *,
    target_date: date,
    event_log: Path = EXPERIMENT_TRACKER_EVENT_LOG_PATH,
) -> list[dict[str, object]]:
    if not event_log.exists():
        return []
    tasks: list[dict[str, object]] = []
    for line in event_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = record.get("event")
        if event not in {"experiment.run_failed", "experiment.data_mismatch_detected"}:
            continue
        run_id = record.get("run_id", "n/a")
        task = "Investigate experiment run failure"
        if event == "experiment.data_mismatch_detected":
            task = "Investigate experiment data mismatch"
        tasks.append(
            {
                "task": task,
                "owner": "research",
                "due": str(target_date),
                "estimate_min": 45,
                "last_worklog": run_id,
                "notes": record.get("reason") or record.get("event"),
            }
        )
    return tasks


def _collect_regression_backtest_tasks(
    *, target_date: date, metrics_path: Path = REGRESSION_BACKTEST_METRICS_PATH
) -> list[dict[str, object]]:
    if not metrics_path.exists():
        return []
    latest: dict[str, object] | None = None
    for line in metrics_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            latest = json.loads(line)
        except json.JSONDecodeError:
            continue
    if not latest:
        return []
    status = latest.get("status")
    if status == "pass":
        return []
    return [
        {
            "task": "Review regression backtest drift",
            "owner": "research",
            "due": str(target_date),
            "estimate_min": 60,
            "last_worklog": latest.get("run_id", "n/a"),
            "notes": f"status={status} drift_count={latest.get('drift_count', 0)}",
        }
    ]


def _collect_broker_monitor_tasks(
    *, target_date: date, alert_log: Path = BROKER_ALERT_EVENT_LOG_PATH
) -> list[dict[str, object]]:
    if not alert_log.exists():
        return []
    tasks: list[dict[str, object]] = []
    for line in alert_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        severity = str(record.get("severity") or "")
        if severity not in {"warning", "critical"}:
            continue
        code = record.get("code", "broker_alert")
        task = "Review broker API alerts"
        if severity == "critical":
            task = "Immediate broker API recovery"
        tasks.append(
            {
                "task": task,
                "owner": "ops",
                "due": str(target_date),
                "estimate_min": 30 if severity == "warning" else 60,
                "last_worklog": record.get("alert_id", "n/a"),
                "notes": f"{code}: {record.get('message', '')}",
            }
        )
    return tasks


def _collect_autonomy_stage_tasks(
    *, target_date: date, event_log: Path = AUTONOMY_STAGE_EVENT_LOG_PATH
) -> list[dict[str, object]]:
    if not event_log.exists():
        return []
    tasks: list[dict[str, object]] = []
    for line in event_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("event") != "autonomy_stage.review_needed":
            continue
        stage = record.get("stage", "unknown")
        tasks.append(
            {
                "task": f"Review autonomy stage ({stage})",
                "owner": "ops",
                "due": str(target_date),
                "estimate_min": 30,
                "last_worklog": record.get("ts", "n/a"),
                "notes": "StageGuard review needed",
            }
        )
    return tasks


def _collect_ops_agenda_events(
    *, target_date: date, event_log: Path = OPS_AGENDA_EVENT_LOG_PATH
) -> list[dict[str, object]]:
    if not event_log.exists():
        return []
    tasks: list[dict[str, object]] = []
    for line in event_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = record.get("event")
        if event not in {"ops.agenda.todo", "ops.agenda.task_added"}:
            continue
        due = record.get("due") or str(target_date)
        tasks.append(
            {
                "task": record.get("task") or "Ops follow-up",
                "owner": record.get("owner") or "ops",
                "due": due,
                "estimate_min": int(record.get("estimate_min", 45)),
                "last_worklog": record.get("ts", "n/a"),
                "notes": record.get("runbook_ref") or record.get("source") or "ops.agenda",
            }
        )
    return tasks


def _collect_access_review_tasks(
    *, target_date: date, reviews_path: Path = ACCESS_REVIEW_REGISTRY_PATH
) -> list[dict[str, object]]:
    if not reviews_path.exists():
        return []
    latest: dict[str, dict[str, object]] = {}
    for line in reviews_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        review_id = record.get("review_id")
        if not review_id:
            continue
        latest[str(review_id)] = record
    tasks: list[dict[str, object]] = []
    for review_id, record in latest.items():
        status = record.get("status") or "unknown"
        if status == "completed":
            continue
        due_at = _parse_due_date(record.get("due_at"))
        due_missing = False
        if due_at is None:
            due_at = target_date
            due_missing = True
        if due_at > target_date:
            continue
        notes = f"scope={record.get('scope') or 'n/a'} status={status}"
        if due_missing:
            notes = f"{notes} due_at=missing"
        tasks.append(
            {
                "task": f"Complete access review {review_id}",
                "owner": record.get("initiated_by") or "security",
                "due": due_at.isoformat(),
                "estimate_min": 60,
                "last_worklog": record.get("initiated_at", "n/a"),
                "notes": notes,
            }
        )
    return tasks


def _parse_due_date(value: object) -> date | None:
    if not value:
        return None
    text = str(value)
    try:
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _idea_pipeline_enabled() -> bool:
    path = Path("config") / "feature_flags.yaml"
    if not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") if isinstance(payload, dict) else None
    if not isinstance(defaults, dict):
        return False
    profile = os.getenv("TRADECTL_PROFILE", "live")
    profile_defaults = defaults.get(profile)
    if not isinstance(profile_defaults, dict):
        return False
    return bool(profile_defaults.get("governance.idea_pipeline_enabled", False))


def _hash_text(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
