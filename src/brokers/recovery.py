"""Order recovery planner for broker API errors."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.brokers.order_store import RecoveryAction, RecoveryPlan

DEFAULT_ERROR_MAP = Path("config/brokers/error_map.yaml")
DEFAULT_RECOVERY_CONFIG = Path("config/brokers/recovery.yaml")
DEFAULT_AUDIT_LOG = Path("logs/audit/order_recovery.jsonl")


@dataclass(slots=True)
class RetryPolicy:
    mode: str
    max_attempts: int
    backoff_sec: list[int] | None = None
    handoff_role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "max_attempts": self.max_attempts,
            "backoff_sec": list(self.backoff_sec or []),
            "handoff_role": self.handoff_role,
        }


@dataclass(slots=True)
class BrokerErrorDescriptor:
    broker_code: str
    trigger_reason: str
    audit_event_id: str
    runbook_ref: str
    retry_policy: RetryPolicy
    evidence_path_template: str
    required_context: list[str]


@dataclass(slots=True)
class ErrorContext:
    broker_code: str
    trigger_reason: str
    audit_event_id: str
    runbook_ref: str
    retry_policy: RetryPolicy
    evidence_path: str
    context_data: dict[str, Any]
    notes: list[str] = field(default_factory=list)


class RecoveryPlannerError(RuntimeError):
    """Raised when recovery planning fails."""


class RecoveryPlanner:
    def __init__(
        self,
        *,
        error_map_path: Path = DEFAULT_ERROR_MAP,
        config_path: Path = DEFAULT_RECOVERY_CONFIG,
        audit_log_path: Path = DEFAULT_AUDIT_LOG,
    ) -> None:
        self._error_map_path = error_map_path
        self._config_path = config_path
        self._audit_log_path = audit_log_path
        self._error_map = _load_error_map(error_map_path)
        self._config = _load_config(config_path)

    def lookup_error(self, code: str) -> BrokerErrorDescriptor | None:
        return self._error_map.get(code)

    def plan(
        self,
        *,
        order_id: str,
        broker_code: str,
        stage_guard_stage: str,
        attempt_count: int,
        last_attempt_ts: str | None,
        context: Mapping[str, Any] | None = None,
    ) -> tuple[RecoveryPlan, ErrorContext]:
        descriptor = self._error_map.get(broker_code)
        if descriptor is None:
            descriptor = self._error_map.get("UNKNOWN")
        if descriptor is None:
            raise RecoveryPlannerError(f"missing error map for {broker_code}")

        context_data = dict(context or {})
        context_data.update(
            {
                "stage_guard_stage": stage_guard_stage,
                "attempt_count": attempt_count,
                "last_attempt_ts": last_attempt_ts,
            }
        )
        missing = [key for key in descriptor.required_context if key not in context_data]
        notes: list[str] = []
        if missing:
            notes.append(f"missing_context:{','.join(missing)}")
            descriptor = self._error_map.get("UNKNOWN", descriptor)
        evidence_path = descriptor.evidence_path_template.replace("<order_id>", order_id)
        error_ctx = ErrorContext(
            broker_code=broker_code,
            trigger_reason=descriptor.trigger_reason,
            audit_event_id=descriptor.audit_event_id,
            runbook_ref=descriptor.runbook_ref,
            retry_policy=descriptor.retry_policy,
            evidence_path=evidence_path,
            context_data=context_data,
            notes=notes,
        )
        actions = _actions_for_trigger(descriptor.trigger_reason, error_ctx.retry_policy)
        plan = RecoveryPlan(
            order_id=order_id,
            plan_id=f"recovery-{uuid.uuid4().hex[:10]}",
            trigger_reason=descriptor.trigger_reason,
            actions=actions,
            assigned_to=self._config.get("default_owner"),
            runbook_ref=descriptor.runbook_ref,
            status="planned",
            created_at=_utcnow_iso(),
            updated_at=_utcnow_iso(),
            notes=[
                f"broker_code={broker_code}",
                f"retry_policy={json.dumps(descriptor.retry_policy.to_dict(), ensure_ascii=False)}",
                *notes,
            ],
        )
        self._append_audit(
            {
                "event": descriptor.audit_event_id,
                "ts": _utcnow_iso(),
                "order_id": order_id,
                "trigger_reason": descriptor.trigger_reason,
                "broker_code": broker_code,
                "runbook_ref": descriptor.runbook_ref,
                "evidence_path": evidence_path,
            }
        )
        if missing:
            self._append_audit(
                {
                    "event": "audit.order_recovery_planned.context_missing",
                    "ts": _utcnow_iso(),
                    "order_id": order_id,
                    "missing": missing,
                    "broker_code": broker_code,
                }
            )
        return plan, error_ctx

    def recovery_sla_minutes(self) -> int:
        return int(self._config.get("sla_minutes", 120))

    def max_recovery_seconds(self) -> int:
        return int(self._config.get("max_sec", 7200))

    def _append_audit(self, payload: Mapping[str, Any]) -> None:
        self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _actions_for_trigger(trigger_reason: str, retry_policy: RetryPolicy) -> list[RecoveryAction]:
    if trigger_reason == "rate_limit":
        return [
            RecoveryAction(code="wait", label="Wait for rate-limit cooldown"),
            RecoveryAction(
                code="retry",
                label="Retry order submission",
                parameters={"max_attempts": retry_policy.max_attempts},
            ),
        ]
    if trigger_reason == "timeout":
        return [
            RecoveryAction(code="emergency_plan", label="Trigger api_retry plan", requires_manual=True),
            RecoveryAction(code="retry", label="Retry after approval", requires_manual=True),
        ]
    if trigger_reason == "partial_fill_timeout":
        return [
            RecoveryAction(
                code="reduce_only", label="Convert remaining qty to reduce-only", requires_manual=True
            )
        ]
    if trigger_reason == "broker_reject":
        return [
            RecoveryAction(code="review", label="Review compliance rejection", requires_manual=True)
        ]
    return [
        RecoveryAction(code="escalate", label="Escalate to ops manager", requires_manual=True)
    ]


def _load_error_map(path: Path) -> dict[str, BrokerErrorDescriptor]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_map = payload.get("error_map") if isinstance(payload, Mapping) else None
    if not isinstance(raw_map, Mapping):
        return {}
    mapping: dict[str, BrokerErrorDescriptor] = {}
    for key, value in raw_map.items():
        if not isinstance(value, Mapping):
            continue
        retry_policy = _parse_retry_policy(value.get("retry_policy"))
        mapping[str(key)] = BrokerErrorDescriptor(
            broker_code=str(key),
            trigger_reason=str(value.get("trigger_reason")),
            audit_event_id=str(value.get("audit_event_id")),
            runbook_ref=str(value.get("runbook_ref")),
            retry_policy=retry_policy,
            evidence_path_template=str(value.get("evidence_path_template")),
            required_context=list(value.get("required_context") or []),
        )
    return mapping


def _parse_retry_policy(payload: Any) -> RetryPolicy:
    data = payload if isinstance(payload, Mapping) else {}
    return RetryPolicy(
        mode=str(data.get("mode", "manual")),
        max_attempts=int(data.get("max_attempts", 1)),
        backoff_sec=list(data.get("backoff_sec") or []) or None,
        handoff_role=data.get("handoff_role"),
    )


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "BrokerErrorDescriptor",
    "ErrorContext",
    "RecoveryPlanner",
    "RetryPolicy",
]
