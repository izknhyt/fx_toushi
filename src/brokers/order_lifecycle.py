"""Order lifecycle manager integrating stage guard, monitor, and recovery planning."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Mapping

from src.brokers.fill_shadow import FillShadowRecorder
from src.brokers.monitor import BrokerApiMonitor, RateLimitWindow
from src.brokers.order_store import OrderEnvelope, OrderState, OrderStateStore, RecoveryPlan
from src.brokers.recovery import RecoveryPlanner
from src.brokers.stage_guard import AutonomyStageGuard
from src.core.health import HealthMonitor
from src.execution.order_router import OrderDispatchRejected

DEFAULT_AUDIT_LOG = Path("logs/audit/order_lifecycle.jsonl")
DEFAULT_METRICS_PATH = Path("metrics/broker_orders.jsonl")
DEFAULT_OPS_AGENDA_LOG = Path("logs/events/ops.agenda.jsonl")


@dataclass(slots=True)
class OrderCompletionReceipt:
    order_id: str
    status: str
    completed_at: str
    evidence_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "status": self.status,
            "completed_at": self.completed_at,
            "evidence_hash": self.evidence_hash,
        }


class OrderLifecycleManager:
    """Manage order envelopes, state transitions, and recovery plans."""

    def __init__(
        self,
        *,
        store: OrderStateStore | None = None,
        stage_guard: AutonomyStageGuard | None = None,
        rate_limiter: RateLimitWindow | None = None,
        monitor: BrokerApiMonitor | None = None,
        fill_shadow: FillShadowRecorder | None = None,
        recovery_planner: RecoveryPlanner | None = None,
        audit_log_path: Path = DEFAULT_AUDIT_LOG,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        ops_agenda_log: Path = DEFAULT_OPS_AGENDA_LOG,
    ) -> None:
        self._store = store or OrderStateStore()
        self._stage_guard = stage_guard or AutonomyStageGuard()
        self._rate_limiter = rate_limiter
        self._monitor = monitor or BrokerApiMonitor()
        self._fill_shadow = fill_shadow or FillShadowRecorder()
        self._recovery_planner = recovery_planner or RecoveryPlanner()
        self._audit_log_path = audit_log_path
        self._metrics_path = metrics_path
        self._ops_agenda_log = ops_agenda_log

    def create(self, ticket: Mapping[str, Any], *, stage_guard_ctx: Mapping[str, Any] | None = None) -> OrderEnvelope:
        stage = str(stage_guard_ctx.get("stage") if stage_guard_ctx else self._stage_guard.stage)
        if stage == "manual_only":
            raise OrderDispatchRejected("stage_manual_only", runbook_ref="RUN-BROKER-API-03")
        reduce_only = bool(ticket.get("reduce_only", False))
        if stage == "reduce_only" and not reduce_only:
            raise OrderDispatchRejected("stage_reduce_only_required", runbook_ref="RUN-RISK-01")

        order_id = f"order-{uuid.uuid4().hex[:12]}"
        envelope = OrderEnvelope(
            order_id=order_id,
            external_id=ticket.get("external_id"),
            mode=str(ticket.get("mode", "paper")),
            stage_guard_stage=stage,
            strategy_id=ticket.get("strategy_id"),
            ticket_id=ticket.get("ticket_id"),
            profile=str(ticket.get("profile", ticket.get("mode", "paper"))),
            risk_snapshot=dict(ticket.get("risk_snapshot") or {}),
            protect_pips=ticket.get("protect_pips"),
            reduce_only=reduce_only,
            submitted_by=str(ticket.get("submitted_by", "system")),
            submitted_at=_utcnow_iso(),
        )
        self._store.save_envelope(envelope)
        state = OrderState(
            order_id=order_id,
            status="created",
            last_transition=_utcnow_iso(),
            attempt=1,
            evidence_hash=_default_evidence_hash(order_id),
        )
        self._store.save_state(state, mode=envelope.mode)
        self._append_audit(
            {
                "event": "audit.order_created",
                "ts": _utcnow_iso(),
                "order_id": order_id,
                "stage_guard_stage": stage,
                "ticket_id": envelope.ticket_id,
            }
        )
        return envelope

    def update_state(
        self,
        order_id: str,
        status: str,
        *,
        mode: str,
        payload: Mapping[str, Any] | None = None,
    ) -> OrderState:
        envelope, current = self._store.load(order_id, mode=mode)
        payload = dict(payload or {})
        attempt = int(payload.get("attempt", current.attempt if current else 1))
        if payload.get("increment_attempt"):
            attempt += 1
        evidence_hash = payload.get("evidence_hash") or (current.evidence_hash if current else None)
        if not evidence_hash:
            evidence_hash = _default_evidence_hash(order_id)
        recovery_plan = payload.get("recovery_plan")
        state = OrderState(
            order_id=order_id,
            status=status,
            last_transition=_utcnow_iso(),
            attempt=attempt,
            evidence_hash=str(evidence_hash),
            error_code=payload.get("error_code"),
            retry_after=payload.get("retry_after"),
            ack_received_at=payload.get("ack_received_at"),
            fill_summary=payload.get("fill_summary"),
            recovery_plan=recovery_plan,
        )
        self._store.save_state(state, mode=mode)
        self._append_audit(
            {
                "event": "audit.order_state_changed",
                "ts": _utcnow_iso(),
                "order_id": order_id,
                "status": status,
                "stage_guard_stage": envelope.stage_guard_stage if envelope else None,
                "runbook_ref": payload.get("runbook_ref"),
            }
        )
        self._append_metrics(
            {
                "order_id": order_id,
                "status": status,
                "stage_guard_stage": envelope.stage_guard_stage if envelope else None,
                "latency_ms": payload.get("latency_ms"),
                "queue_wait_ms": payload.get("queue_wait_ms"),
                "retry_after": payload.get("retry_after"),
            }
        )
        if status == "queued" and payload.get("queue_wait_ms"):
            wait_ms = float(payload.get("queue_wait_ms"))
            if wait_ms > 0:
                self._monitor.record_queue_wait(
                    adapter=str(payload.get("adapter", "unknown")),
                    operation="order.place",
                    wait_sec=wait_ms / 1000.0,
                    queue_depth=int(payload.get("queue_depth", 0)),
                )
                HealthMonitor().raise_condition(
                    "warn",
                    "broker_queue_backlog",
                    detail=f"queue_wait_ms={wait_ms}",
                    recommended_action="runbook:RUN-BROKER-API-02#RL-01",
                )
        return state

    def attach_fill(
        self,
        order_id: str,
        *,
        mode: str,
        fill_event: Mapping[str, Any],
        status: str = "filled",
    ) -> OrderState:
        summary_hash = _hash_payload(fill_event)
        self._fill_shadow.record(
            ticket_id=str(fill_event.get("ticket_id") or ""),
            order_id=str(fill_event.get("order_id") or order_id),
            status=status,
            adapter=str(fill_event.get("adapter") or ""),
            profile=str(fill_event.get("profile") or "paper"),
            payload=dict(fill_event),
        )
        return self.update_state(
            order_id,
            status=status,
            mode=mode,
            payload={
                "fill_summary": summary_hash,
                "ack_received_at": fill_event.get("ack_received_at"),
            },
        )

    def schedule_recovery(
        self,
        order_id: str,
        *,
        mode: str,
        broker_code: str,
        context: Mapping[str, Any] | None = None,
    ) -> tuple[OrderState, RecoveryPlan]:
        envelope, current = self._store.load(order_id, mode=mode)
        stage = envelope.stage_guard_stage if envelope else "manual_only"
        attempt = current.attempt if current else 1
        plan, error_ctx = self._recovery_planner.plan(
            order_id=order_id,
            broker_code=broker_code,
            stage_guard_stage=stage,
            attempt_count=attempt,
            last_attempt_ts=current.last_transition if current else None,
            context=context,
        )
        state = self.update_state(
            order_id,
            status="error",
            mode=mode,
            payload={
                "error_code": broker_code,
                "recovery_plan": plan,
                "runbook_ref": error_ctx.runbook_ref,
            },
        )
        due_at = datetime.now(timezone.utc) + timedelta(
            minutes=self._recovery_planner.recovery_sla_minutes()
        )
        self._append_ops_agenda(
            {
                "event": "ops.agenda.todo",
                "ts": _utcnow_iso(),
                "task": f"Order recovery {order_id}",
                "owner": plan.assigned_to or "ops",
                "due": due_at.date().isoformat(),
                "source": "broker_orders",
                "order_id": order_id,
                "runbook_ref": plan.runbook_ref,
            }
        )
        return state, plan

    def finalize(self, order_id: str, *, mode: str) -> OrderCompletionReceipt:
        envelope, current = self._store.load(order_id, mode=mode)
        state = self.update_state(order_id, status="reconciled", mode=mode)
        receipt = OrderCompletionReceipt(
            order_id=order_id,
            status=state.status,
            completed_at=_utcnow_iso(),
            evidence_hash=state.evidence_hash,
        )
        self._append_audit(
            {
                "event": "audit.order_lifecycle_completed",
                "ts": receipt.completed_at,
                "order_id": order_id,
                "status": state.status,
                "runbook_ref": "RUN-BROKER-API-02",
            }
        )
        return receipt

    def _append_audit(self, payload: Mapping[str, Any]) -> None:
        self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_metrics(self, payload: Mapping[str, Any]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": _utcnow_iso(), **payload}
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")

    def _append_ops_agenda(self, payload: Mapping[str, Any]) -> None:
        self._ops_agenda_log.parent.mkdir(parents=True, exist_ok=True)
        with self._ops_agenda_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _hash_payload(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8"))
    return digest.hexdigest()


def _default_evidence_hash(order_id: str) -> str:
    return hashlib.sha256(order_id.encode("utf-8")).hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["OrderLifecycleManager", "OrderCompletionReceipt"]
