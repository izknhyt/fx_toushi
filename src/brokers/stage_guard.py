"""Autonomy stage guard with evaluation and approval workflow."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml

StageName = Literal["manual_only", "reduce_only", "partial_auto", "full_auto"]

DEFAULT_STATE_PATH = Path("snapshots/latest/autonomy_stage.json")
DEFAULT_AUDIT_LOG = Path("logs/audit/autonomy_stage.jsonl")
DEFAULT_EVENT_LOG = Path("logs/events/autonomy_stage.jsonl")
DEFAULT_OPS_WORKLOG = Path("ops_worklog.jsonl")
DEFAULT_FEATURE_FLAGS = Path("config/feature_flags.yaml")
DEFAULT_READINESS_METRICS = Path("metrics/ops_readiness.jsonl")
DEFAULT_CERTIFICATION_METRICS = Path("metrics/broker_certification.jsonl")
DEFAULT_SHADOW_EVENTS = Path("logs/broker/shadow_events.jsonl")
DEFAULT_FAILOVER_STATE = Path("snapshots/latest/broker_failover.json")
DEFAULT_DRILL_PLANS = Path("logs/ops/drill_plan.jsonl")
DEFAULT_DRILL_EXECUTIONS = Path("logs/ops/drill_execution.jsonl")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class StageTransition:
    """Record of a stage transition for audit/history."""

    from_stage: StageName
    to_stage: StageName
    actor: str
    reason: str | None
    ts: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "actor": self.actor,
            "reason": self.reason,
            "ts": self.ts,
        }


@dataclass(slots=True)
class StageRequest:
    request_id: str
    requested_stage: StageName
    requested_by: str
    requested_at: str
    status: str
    reason: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "requested_stage": self.requested_stage,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at,
            "status": self.status,
            "reason": self.reason,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
        }


@dataclass(slots=True)
class StageGuardContext:
    ops_readiness_score: float | None
    certification_status: str | None
    fill_shadow_alerts: int
    emergency_active: bool
    drill_overdue: bool
    incident_count: int
    risk_disclosure_ok: bool
    stage_guard_enabled: bool
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StageGuardEvaluation:
    allowed_promotions: list[StageName]
    blocks: dict[StageName, list[str]]
    recommended_demotions: list[StageName]
    next_actions: list[str]
    runbook_refs: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_promotions": list(self.allowed_promotions),
            "blocks": {stage: list(reasons) for stage, reasons in self.blocks.items()},
            "recommended_demotions": list(self.recommended_demotions),
            "next_actions": list(self.next_actions),
            "runbook_refs": list(self.runbook_refs),
        }


class StageGuardError(RuntimeError):
    """Raised when a stage guard operation fails."""


class StageRequestNotFound(StageGuardError):
    """Raised when a stage request cannot be located."""


class StageRequestNotApproved(StageGuardError):
    """Raised when a stage request is not in an approvable state."""


class AutonomyStageGuard:
    """Stage guard managing manual_only -> reduce_only -> partial_auto -> full_auto transitions."""

    _allowed_order: tuple[StageName, ...] = (
        "manual_only",
        "reduce_only",
        "partial_auto",
        "full_auto",
    )

    def __init__(
        self,
        *,
        stage: StageName | None = None,
        state_path: Path = DEFAULT_STATE_PATH,
        audit_log_path: Path = DEFAULT_AUDIT_LOG,
        event_log_path: Path = DEFAULT_EVENT_LOG,
        ops_worklog_path: Path = DEFAULT_OPS_WORKLOG,
        feature_flags_path: Path = DEFAULT_FEATURE_FLAGS,
        readiness_metrics_path: Path = DEFAULT_READINESS_METRICS,
        certification_metrics_path: Path = DEFAULT_CERTIFICATION_METRICS,
        shadow_event_log: Path = DEFAULT_SHADOW_EVENTS,
        failover_state_path: Path = DEFAULT_FAILOVER_STATE,
        drill_plan_log: Path = DEFAULT_DRILL_PLANS,
        drill_execution_log: Path = DEFAULT_DRILL_EXECUTIONS,
    ) -> None:
        self._state_path = state_path
        self._audit_log_path = audit_log_path
        self._event_log_path = event_log_path
        self._ops_worklog_path = ops_worklog_path
        self._feature_flags_path = feature_flags_path
        self._readiness_metrics_path = readiness_metrics_path
        self._certification_metrics_path = certification_metrics_path
        self._shadow_event_log = shadow_event_log
        self._failover_state_path = failover_state_path
        self._drill_plan_log = drill_plan_log
        self._drill_execution_log = drill_execution_log
        self.stage: StageName
        self.updated_at: str
        self.updated_by: str
        self._history: list[StageTransition] = []
        self._requests: list[StageRequest] = []
        self._load_state()
        if stage is not None:
            self.stage = stage

    def promote(
        self,
        stage: StageName,
        *,
        actor: str = "system",
        reason: str | None = None,
        context: StageGuardContext | None = None,
        override: bool = False,
    ) -> StageTransition:
        """Promote to the requested stage if it respects ordering and policy."""

        if stage not in self._allowed_order:
            raise StageGuardError(f"Unknown stage: {stage}")
        if not override:
            evaluation = self.evaluate(context or self.load_context())
            if stage not in evaluation.allowed_promotions:
                reasons = ", ".join(evaluation.blocks.get(stage, [])) or "blocked"
                raise StageGuardError(f"Stage promotion blocked: {stage} ({reasons})")
        current_index = self._allowed_order.index(self.stage)
        target_index = self._allowed_order.index(stage)
        if target_index < current_index:
            raise StageGuardError(f"Cannot demote from {self.stage} to {stage}")
        transition = StageTransition(
            from_stage=self.stage,
            to_stage=stage,
            actor=actor,
            reason=reason,
            ts=_utcnow_iso(),
        )
        self._apply_transition(transition)
        self._append_audit(
            {
                "event": "audit.autonomy_stage_changed",
                "stage_from": transition.from_stage,
                "stage_to": transition.to_stage,
                "actor": actor,
                "reason": reason,
                "ts": transition.ts,
            }
        )
        return transition

    def rollback_one(
        self, *, actor: str = "system", reason: str | None = None
    ) -> StageTransition | None:
        """Rollback one stage if possible."""

        current_index = self._allowed_order.index(self.stage)
        if current_index == 0:
            return None
        target_stage = self._allowed_order[current_index - 1]
        transition = StageTransition(
            from_stage=self.stage,
            to_stage=target_stage,
            actor=actor,
            reason=reason,
            ts=_utcnow_iso(),
        )
        self._apply_transition(transition)
        self._append_audit(
            {
                "event": "audit.autonomy_stage_changed",
                "stage_from": transition.from_stage,
                "stage_to": transition.to_stage,
                "actor": actor,
                "reason": reason or "rollback",
                "ts": transition.ts,
            }
        )
        return transition

    def on_error(
        self, error_class: str, *, actor: str = "system", reason: str | None = None
    ) -> StageTransition | None:
        """Handle error classification: circuit_breaker triggers a rollback."""

        if error_class == "circuit_breaker":
            return self.rollback_one(actor=actor, reason=reason or "circuit_breaker")
        return None

    def recover(
        self, *, actor: str = "system", reason: str | None = None
    ) -> StageTransition | None:
        """Promote one step after a circuit breaker resolution."""

        current_index = self._allowed_order.index(self.stage)
        if current_index + 1 >= len(self._allowed_order):
            return None
        target_stage = self._allowed_order[current_index + 1]
        transition = StageTransition(
            from_stage=self.stage,
            to_stage=target_stage,
            actor=actor,
            reason=reason,
            ts=_utcnow_iso(),
        )
        self._apply_transition(transition)
        self._append_audit(
            {
                "event": "audit.autonomy_stage_changed",
                "stage_from": transition.from_stage,
                "stage_to": transition.to_stage,
                "actor": actor,
                "reason": reason or "recover",
                "ts": transition.ts,
            }
        )
        return transition

    def request_transition(
        self,
        stage: StageName,
        *,
        actor: str = "system",
        reason: str | None = None,
    ) -> StageRequest:
        if stage not in self._allowed_order:
            raise StageGuardError(f"Unknown stage: {stage}")
        request = StageRequest(
            request_id=f"stage-{uuid.uuid4().hex[:8]}",
            requested_stage=stage,
            requested_by=actor,
            requested_at=_utcnow_iso(),
            status="requested",
            reason=reason,
        )
        self._requests.append(request)
        self._append_audit(
            {
                "event": "audit.autonomy_stage_request",
                "request_id": request.request_id,
                "requested_stage": stage,
                "requested_by": actor,
                "reason": reason,
                "ts": request.requested_at,
            }
        )
        self._append_event(
            {
                "event": "autonomy_stage.requested",
                "request_id": request.request_id,
                "requested_stage": stage,
                "requested_by": actor,
                "ts": request.requested_at,
            }
        )
        self._append_ops_worklog(
            {
                "timestamp": request.requested_at,
                "task": "autonomy_stage_review",
                "request_id": request.request_id,
                "requested_stage": stage,
                "status": "pending",
                "runbook_ref": "RUN-BROKER-API-03",
            }
        )
        self._save_state()
        return request

    def approve_request(
        self,
        request_id: str,
        *,
        actor: str,
        reason: str | None = None,
        context: StageGuardContext | None = None,
    ) -> StageTransition:
        request = self._find_request(request_id)
        if request.status != "requested":
            raise StageRequestNotApproved(f"Request {request_id} not approvable")
        transition = self.promote(
            request.requested_stage,
            actor=actor,
            reason=reason or request.reason,
            context=context,
        )
        request.status = "approved"
        request.approved_by = actor
        request.approved_at = transition.ts
        self._append_audit(
            {
                "event": "audit.autonomy_stage_approved",
                "request_id": request.request_id,
                "stage": request.requested_stage,
                "approved_by": actor,
                "reason": reason or request.reason,
                "ts": transition.ts,
            }
        )
        self._save_state()
        return transition

    def deny_request(self, request_id: str, *, actor: str, reason: str | None = None) -> StageRequest:
        request = self._find_request(request_id)
        if request.status != "requested":
            raise StageRequestNotApproved(f"Request {request_id} not deniable")
        request.status = "denied"
        request.approved_by = actor
        request.approved_at = _utcnow_iso()
        self._append_audit(
            {
                "event": "audit.autonomy_stage_denied",
                "request_id": request.request_id,
                "stage": request.requested_stage,
                "approved_by": actor,
                "reason": reason,
                "ts": request.approved_at,
            }
        )
        self._append_event(
            {
                "event": "autonomy_stage.denied",
                "request_id": request.request_id,
                "requested_stage": request.requested_stage,
                "denied_by": actor,
                "reason": reason,
                "ts": request.approved_at,
            }
        )
        self._save_state()
        return request

    def evaluate(
        self, context: StageGuardContext, *, emit_events: bool = False
    ) -> StageGuardEvaluation:
        allowed_promotions: list[StageName] = []
        blocks: dict[StageName, list[str]] = {}
        recommended_demotions: list[StageName] = []
        next_actions: list[str] = []
        runbook_refs: list[str] = []

        if not context.stage_guard_enabled:
            for stage in self._allowed_order:
                if stage != self.stage:
                    blocks[stage] = ["feature_flag_disabled"]
            return StageGuardEvaluation(
                allowed_promotions=allowed_promotions,
                blocks=blocks,
                recommended_demotions=recommended_demotions,
                next_actions=["Enable brokers.autonomy_stage_enabled to evaluate stages."],
                runbook_refs=["RUN-BROKER-API-03"],
            )

        for stage in self._allowed_order:
            if self._allowed_order.index(stage) <= self._allowed_order.index(self.stage):
                continue
            reasons = _stage_requirements(stage, context)
            if reasons:
                blocks[stage] = reasons
            else:
                allowed_promotions.append(stage)

        recommended_demotions = _recommended_demotions(self.stage, context)
        if context.emergency_active:
            next_actions.append("Emergency plan active: review API failover status.")
            runbook_refs.append("RUN-BROKER-API-02")
        if context.fill_shadow_alerts:
            next_actions.append("FillShadow alerts detected: review shadow reconciliation.")
            runbook_refs.append("RUN-BROKER-API-02")
        if context.ops_readiness_score is not None and context.ops_readiness_score < 75:
            next_actions.append("Ops readiness below threshold: review ops readiness evidence.")
            runbook_refs.append("OPS-READINESS-01")
        if context.drill_overdue:
            next_actions.append("Emergency drill overdue: schedule drill execution.")
            runbook_refs.append("RUN-BROKER-API-02")

        evaluation = StageGuardEvaluation(
            allowed_promotions=allowed_promotions,
            blocks=blocks,
            recommended_demotions=recommended_demotions,
            next_actions=next_actions,
            runbook_refs=sorted(set(runbook_refs)) or ["RUN-BROKER-API-03"],
        )
        if emit_events:
            self._emit_review_tasks(context, evaluation)
        return evaluation

    def status(self, *, context: StageGuardContext | None = None) -> dict[str, Any]:
        ctx = context or self.load_context()
        evaluation = self.evaluate(ctx, emit_events=True)
        return {
            "stage": self.stage,
            "updated_at": self.updated_at,
            "updated_by": self.updated_by,
            "pending_requests": [request.to_dict() for request in self.pending_requests()],
            "evaluation": evaluation.to_dict(),
            "context": {
                "ops_readiness_score": ctx.ops_readiness_score,
                "certification_status": ctx.certification_status,
                "fill_shadow_alerts": ctx.fill_shadow_alerts,
                "emergency_active": ctx.emergency_active,
                "drill_overdue": ctx.drill_overdue,
                "incident_count": ctx.incident_count,
                "risk_disclosure_ok": ctx.risk_disclosure_ok,
                "stage_guard_enabled": ctx.stage_guard_enabled,
                "notes": list(ctx.notes),
            },
        }

    def pending_requests(self) -> list[StageRequest]:
        return [request for request in self._requests if request.status == "requested"]

    def history(self) -> list[StageTransition]:
        return list(self._history)

    def load_context(self) -> StageGuardContext:
        notes: list[str] = []
        ops_readiness_score = _load_ops_readiness_score(self._readiness_metrics_path)
        if ops_readiness_score is None:
            notes.append("ops_readiness_score:missing")
        certification_status = _load_certification_status(self._certification_metrics_path)
        if certification_status is None:
            notes.append("broker_certification:missing")
        fill_shadow_alerts = _count_fill_shadow_alerts(self._shadow_event_log)
        emergency_active = _load_failover_active(self._failover_state_path)
        drill_overdue = _drill_overdue(self._drill_plan_log, self._drill_execution_log)
        return StageGuardContext(
            ops_readiness_score=ops_readiness_score,
            certification_status=certification_status,
            fill_shadow_alerts=fill_shadow_alerts,
            emergency_active=emergency_active,
            drill_overdue=drill_overdue,
            incident_count=0,
            risk_disclosure_ok=True,
            stage_guard_enabled=_load_feature_flag(
                "brokers.autonomy_stage_enabled", self._feature_flags_path
            ),
            notes=notes,
        )

    def _apply_transition(self, transition: StageTransition) -> None:
        self.stage = transition.to_stage
        self.updated_at = transition.ts
        self.updated_by = transition.actor
        self._history.append(transition)
        self._save_state()

    def _load_state(self) -> None:
        if not self._state_path.exists():
            self.stage = "manual_only"
            self.updated_at = _utcnow_iso()
            self.updated_by = "system"
            return
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.stage = "manual_only"
            self.updated_at = _utcnow_iso()
            self.updated_by = "system"
            return
        stage_value = payload.get("stage") or "manual_only"
        self.stage = stage_value if stage_value in self._allowed_order else "manual_only"
        self.updated_at = payload.get("updated_at") or _utcnow_iso()
        self.updated_by = payload.get("updated_by") or "system"
        history_payload = payload.get("history") or []
        self._history = [
            StageTransition(
                from_stage=entry.get("from_stage", "manual_only"),
                to_stage=entry.get("to_stage", "manual_only"),
                actor=entry.get("actor", "system"),
                reason=entry.get("reason"),
                ts=entry.get("ts", _utcnow_iso()),
            )
            for entry in history_payload
            if isinstance(entry, Mapping)
        ]
        request_payload = payload.get("requests") or []
        self._requests = [
            StageRequest(
                request_id=str(entry.get("request_id")),
                requested_stage=entry.get("requested_stage"),
                requested_by=entry.get("requested_by", "system"),
                requested_at=entry.get("requested_at", _utcnow_iso()),
                status=entry.get("status", "requested"),
                reason=entry.get("reason"),
                approved_by=entry.get("approved_by"),
                approved_at=entry.get("approved_at"),
            )
            for entry in request_payload
            if isinstance(entry, Mapping)
        ]

    def _save_state(self) -> None:
        payload = {
            "stage": self.stage,
            "updated_at": self.updated_at,
            "updated_by": self.updated_by,
            "history": [transition.to_dict() for transition in self._history],
            "requests": [request.to_dict() for request in self._requests],
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _find_request(self, request_id: str) -> StageRequest:
        for request in self._requests:
            if request.request_id == request_id:
                return request
        raise StageRequestNotFound(request_id)

    def _append_audit(self, payload: Mapping[str, Any]) -> None:
        self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_event(self, payload: Mapping[str, Any]) -> None:
        self._event_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._event_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_ops_worklog(self, payload: Mapping[str, Any]) -> None:
        self._ops_worklog_path.parent.mkdir(parents=True, exist_ok=True)
        with self._ops_worklog_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _emit_review_tasks(self, context: StageGuardContext, evaluation: StageGuardEvaluation) -> None:
        if not evaluation.recommended_demotions and not evaluation.blocks:
            return
        event_payload = {
            "event": "autonomy_stage.review_needed",
            "ts": _utcnow_iso(),
            "stage": self.stage,
            "recommended_demotions": evaluation.recommended_demotions,
            "blocks": evaluation.blocks,
            "ops_readiness_score": context.ops_readiness_score,
            "certification_status": context.certification_status,
            "fill_shadow_alerts": context.fill_shadow_alerts,
            "emergency_active": context.emergency_active,
            "drill_overdue": context.drill_overdue,
            "runbook_refs": evaluation.runbook_refs,
        }
        if self._should_emit_event(event_payload):
            self._append_event(event_payload)
            self._append_ops_worklog(
                {
                    "timestamp": event_payload["ts"],
                    "task": "autonomy_stage_review",
                    "status": "needed",
                    "stage": self.stage,
                    "runbook_ref": "RUN-BROKER-API-03",
                }
            )

    def _should_emit_event(self, payload: Mapping[str, Any]) -> bool:
        if not self._event_log_path.exists():
            return True
        lines = [line for line in self._event_log_path.read_text(encoding="utf-8").splitlines() if line]
        if not lines:
            return True
        try:
            last = json.loads(lines[-1])
        except json.JSONDecodeError:
            return True
        if last.get("event") != payload.get("event"):
            return True
        try:
            last_ts = _parse_ts(str(last.get("ts")))
        except Exception:
            return True
        if not last_ts:
            return True
        return datetime.now(timezone.utc) - last_ts > timedelta(hours=1)


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stage_requirements(stage: StageName, context: StageGuardContext) -> list[str]:
    reasons: list[str] = []
    if stage == "reduce_only":
        if context.ops_readiness_score is None or context.ops_readiness_score < 70:
            reasons.append("ops_readiness_score<70")
        if context.certification_status not in {"pass", "pass_with_warning"}:
            reasons.append("broker_certification_not_pass")
        if context.fill_shadow_alerts:
            reasons.append("fill_shadow_alerts")
        if not context.risk_disclosure_ok:
            reasons.append("risk_disclosure_pending")
    elif stage == "partial_auto":
        if context.ops_readiness_score is None or context.ops_readiness_score < 80:
            reasons.append("ops_readiness_score<80")
        if context.drill_overdue:
            reasons.append("emergency_drill_overdue")
        if context.emergency_active:
            reasons.append("emergency_active")
    elif stage == "full_auto":
        reasons.append("requires_m3_soak")
    return reasons


def _recommended_demotions(stage: StageName, context: StageGuardContext) -> list[StageName]:
    recommended: list[StageName] = []
    if context.emergency_active and stage != "manual_only":
        return ["manual_only"]
    if context.fill_shadow_alerts and stage in {"partial_auto", "full_auto"}:
        recommended.append("reduce_only")
    if context.ops_readiness_score is not None and context.ops_readiness_score < 75:
        if stage in {"partial_auto", "full_auto"} and "reduce_only" not in recommended:
            recommended.append("reduce_only")
    if context.drill_overdue and stage in {"partial_auto", "full_auto"}:
        if "reduce_only" not in recommended:
            recommended.append("reduce_only")
    return recommended


def _load_feature_flag(flag: str, path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") if isinstance(payload, Mapping) else None
    if not isinstance(defaults, Mapping):
        return False
    for profile in ("live", "paper", "backtest"):
        profile_flags = defaults.get(profile)
        if isinstance(profile_flags, Mapping) and profile_flags.get(flag) is True:
            return True
    return False


def _load_ops_readiness_score(path: Path) -> float | None:
    if not path.exists():
        return None
    last_line = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last_line = line
    if not last_line:
        return None
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError:
        return None
    score = payload.get("readiness_score")
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def _load_certification_status(path: Path) -> str | None:
    if not path.exists():
        return None
    last_line = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last_line = line
    if not last_line:
        return None
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError:
        return None
    status = payload.get("status")
    return str(status) if status else None


def _count_fill_shadow_alerts(path: Path, *, hours: int = 24) -> int:
    if not path.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") != "shadow.fill_drift_detected":
            continue
        ts = _parse_ts(str(payload.get("ts") or ""))
        if ts and ts < cutoff:
            continue
        if str(payload.get("severity")) == "major":
            count += 1
    return count


def _load_failover_active(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    status = str(payload.get("status") or "")
    return status in {"blocked", "active", "triggered"}


def _drill_overdue(plans_path: Path, executions_path: Path) -> bool:
    plans = _load_drill_plans(plans_path)
    if not plans:
        return False
    completion = _load_drill_completion(executions_path)
    now = datetime.now(timezone.utc)
    for plan in plans:
        plan_id = plan.get("plan_id")
        if not plan_id:
            continue
        scheduled_for = plan.get("scheduled_for")
        if not isinstance(scheduled_for, datetime):
            continue
        if scheduled_for > now:
            continue
        status = completion.get(str(plan_id))
        if status not in {"completed", "completed_with_notes"}:
            return True
    return False


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
        scheduled_for = _parse_ts(str(data.get("scheduled_for") or ""))
        if scheduled_for is None:
            scheduled_for = datetime.now(timezone.utc)
        plans.append({"plan_id": data.get("plan_id"), "scheduled_for": scheduled_for})
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
        plan_id = data.get("plan_id") or _plan_id_from_execution_id(str(execution_id))
        status = data.get("status")
        if plan_id and status:
            completion[str(plan_id)] = str(status)
    return completion


def _plan_id_from_execution_id(execution_id: str) -> str:
    if execution_id.endswith("-run"):
        return execution_id[:-4]
    return execution_id


__all__ = [
    "AutonomyStageGuard",
    "StageGuardContext",
    "StageGuardEvaluation",
    "StageName",
    "StageRequest",
    "StageRequestNotApproved",
    "StageRequestNotFound",
    "StageTransition",
]
