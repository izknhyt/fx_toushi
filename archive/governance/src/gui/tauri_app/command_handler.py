"""Command handler that bridges GUI actions to CLI flows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from src.core.gate import GateState
from src.interfaces.cli import tickets as ticket_actions
from src.interfaces.gui.tauri_app.audit import GuiAuditWriter
from src.interfaces.gui.tauri_app.event_bridge import GuiEventBridge

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ActionRequest:
    action: str
    ticket_id: str
    payload: dict[str, Any]


@dataclass(slots=True)
class ActionResponse:
    status: str
    action: str
    ticket_id: str
    result: Mapping[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "action": self.action,
            "ticket_id": self.ticket_id,
            "result": dict(self.result) if self.result else None,
            "error": self.error,
        }


class GuiCommandHandler:
    def __init__(
        self,
        *,
        event_bridge: GuiEventBridge | None = None,
        audit_writer: GuiAuditWriter | None = None,
    ) -> None:
        self._event_bridge = event_bridge
        self._audit_writer = audit_writer or GuiAuditWriter()

    def execute(self, request: ActionRequest) -> ActionResponse:
        action = request.action
        ticket_id = request.ticket_id
        payload = request.payload
        try:
            gate_state = _parse_gate_state(payload.get("gate_state"))
            if action == "ticket.approve":
                result = ticket_actions.approve(
                    ticket_id,
                    note=payload.get("note"),
                    user=payload.get("user"),
                    force_consent=bool(payload.get("force_consent", False)),
                    consent_reference_id=payload.get("consent_reference_id"),
                    double_entry_user=payload.get("double_entry_user"),
                    require_double_entry=bool(payload.get("require_double_entry", False)),
                    take_over=bool(payload.get("take_over", False)),
                    board_mode=str(payload.get("board_mode") or "normal"),
                    guardrails=payload.get("guardrails"),
                    gate_state=gate_state,
                    determinism_hash=payload.get("determinism_hash"),
                    determinism_version=int(payload.get("determinism_version", 1)),
                )
            elif action == "ticket.reject":
                result = ticket_actions.reject(
                    ticket_id,
                    reason=payload.get("reason"),
                    user=payload.get("user"),
                    take_over=bool(payload.get("take_over", False)),
                    board_mode=str(payload.get("board_mode") or "normal"),
                    guardrails=payload.get("guardrails"),
                    gate_state=gate_state,
                )
            elif action == "ticket.defer":
                result = ticket_actions.edit(
                    ticket_id,
                    field="status",
                    value="deferred",
                    user=payload.get("user"),
                    take_over=bool(payload.get("take_over", False)),
                    board_mode=str(payload.get("board_mode") or "normal"),
                    guardrails=payload.get("guardrails"),
                    gate_state=gate_state,
                    determinism_hash=payload.get("determinism_hash"),
                    determinism_version=int(payload.get("determinism_version", 1)),
                )
            else:
                raise ValueError(f"unsupported action: {action}")

            response = ActionResponse(
                status="ok",
                action=action,
                ticket_id=ticket_id,
                result=result,
            )
            self._publish("command.success", response.to_dict())
            self._audit_writer.record(
                action=action,
                ticket_id=ticket_id,
                user=str(payload.get("user") or "unknown"),
                status="ok",
                source="tauri",
                category=_category_for_action(action),
                delta=_build_delta(result, decision="ok"),
            )
            return response
        except Exception as exc:  # noqa: BLE001
            logger.error("gui.command_handler.failed", extra={"action": action, "error": str(exc)})
            response = ActionResponse(
                status="error",
                action=action,
                ticket_id=ticket_id,
                error=str(exc),
            )
            self._publish("command.error", response.to_dict())
            self._audit_writer.record(
                action=action,
                ticket_id=ticket_id,
                user=str(payload.get("user") or "unknown"),
                status="error",
                source="tauri",
                category=_category_for_action(action),
                delta=_build_delta(None, decision="error"),
                error=str(exc),
            )
            return response

    def _publish(self, event_type: str, payload: Mapping[str, Any]) -> None:
        if not self._event_bridge:
            return
        self._event_bridge.publish(event_type, dict(payload))


def _parse_gate_state(value: Any) -> GateState | None:
    if isinstance(value, GateState):
        return value
    if isinstance(value, dict):
        return GateState.from_dict(value)
    return None


def _category_for_action(action: str) -> str:
    if action.startswith("ticket."):
        return "gui.ticket"
    if action.startswith("command."):
        return "gui.command"
    return "gui.state"


def _build_delta(result: Mapping[str, Any] | None, *, decision: str) -> Mapping[str, Any]:
    if result is None:
        return {"before": None, "after": None, "diff": {}, "decision": decision}
    before = result.get("before")
    after = result.get("after")
    diff = result.get("diff", {})
    decision_value = result.get("decision", decision)
    return {
        "before": before,
        "after": after,
        "diff": diff if isinstance(diff, Mapping) else {},
        "decision": decision_value,
    }


__all__ = ["ActionRequest", "ActionResponse", "GuiCommandHandler"]
