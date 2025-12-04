"""Serializer helpers to expose TicketRecord v2 payloads to the Tauri frontend."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.interfaces.cli.board import board as board_view
from src.interfaces.cli.kill_switch import set_state as cli_kill_switch_set
from src.ticket import TicketRecord, TicketRecordAdapter

logger = logging.getLogger(__name__)


class TicketPayloadSerializer:
    """Normalize ticket payloads for GUI consumption (v2 contract)."""

    version: int = 2

    @classmethod
    def to_dict(cls, ticket: TicketRecord | Mapping[str, Any]) -> Mapping[str, Any]:
        """Return a serialisable dict with `ticket_payload_version` included."""

        record = ticket
        if not isinstance(ticket, TicketRecord):
            record = TicketRecordAdapter.from_v1(ticket)  # type: ignore[assignment]
        payload = record.to_dict()  # type: ignore[union-attr]
        payload["ticket_payload_version"] = cls.version
        return payload

    @classmethod
    def bulk(cls, tickets: Iterable[TicketRecord | Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        return [cls.to_dict(ticket) for ticket in tickets]


def board_get_snapshot(
    *,
    tickets: Sequence[TicketRecord | Mapping[str, Any]] = (),
    gate_state_path: Path | None = None,
    manifest_path: Path = Path("reports/data_manifest.json"),
    board_kwargs: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Compose the snapshot payload returned via IPC.

    - tickets are normalized to TicketRecord v2
    - board payload is reused from CLI for banner/guardrail parity
    """

    board_payload = board_view(manifest_path=manifest_path, **(board_kwargs or {}))
    ticket_payloads = TicketPayloadSerializer.bulk(tickets)
    snapshot: dict[str, Any] = {
        "ticket_payload_version": TicketPayloadSerializer.version,
        "board": board_payload,
        "tickets": ticket_payloads,
        "gate_state_path": str(gate_state_path) if gate_state_path else None,
    }
    logger.info(
        "gui.board_get_snapshot",
        extra={"ticket_count": len(ticket_payloads), "compat": board_payload.get("compat_mode")},
    )
    return snapshot


def kill_switch_set(
    *,
    state: str,
    reason: str | None = None,
    actor: str | None = None,
    runbook: str | None = None,
) -> Mapping[str, Any]:
    """IPC handler delegating to CLI kill-switch set implementation."""

    try:
        cli_kill_switch_set(state=state, reason=reason, actor=actor, runbook=runbook)
        status = "accepted"
    except Exception as exc:  # noqa: BLE001
        logger.error("gui.kill_switch_set.failed", extra={"state": state, "error": str(exc)})
        status = "error"
    payload = {
        "state": state,
        "reason": reason,
        "actor": actor,
        "runbook": runbook,
        "status": status,
    }
    return payload


__all__ = ["TicketPayloadSerializer", "board_get_snapshot", "kill_switch_set"]
