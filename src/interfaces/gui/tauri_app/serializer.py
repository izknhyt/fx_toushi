"""Serializer helpers for TicketRecord v2 payloads and EventBus snapshots.

Used by the Tauri frontend.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.core.event_bus import EventBus, EventBusConfig
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
    event_bus: EventBus | None = None,
    ticket_action_log: Path | None = Path("logs/audit/ticket_action.jsonl"),
    events_lookback: timedelta = timedelta(days=7),
    max_events_per_channel: int = 10,
) -> Mapping[str, Any]:
    """Compose the snapshot payload returned via IPC.

    - tickets are normalized to TicketRecord v2
    - board payload is reused from CLI for banner/guardrail parity
    - recent_events bundles last events per channel for initial render (EventBus + ticket.action
      audit)
    """

    board_payload = board_view(manifest_path=manifest_path, **(board_kwargs or {}))
    ticket_payloads = TicketPayloadSerializer.bulk(tickets)
    bus = event_bus or EventBus(EventBusConfig())
    recent_events = collect_recent_events(
        bus,
        from_ts=datetime.utcnow() - events_lookback,
        per_channel_limit=max_events_per_channel,
        ticket_action_log=ticket_action_log,
    )

    snapshot: dict[str, Any] = {
        "ticket_payload_version": TicketPayloadSerializer.version,
        "board": board_payload,
        "tickets": ticket_payloads,
        "gate_state_path": str(gate_state_path) if gate_state_path else None,
        "recent_events": recent_events,
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


def collect_recent_events(
    event_bus: EventBus,
    *,
    from_ts: datetime,
    to_ts: datetime | None = None,
    per_channel_limit: int = 10,
    ticket_action_log: Path | None = Path("logs/audit/ticket_action.jsonl"),
    fill_placeholders: bool = True,
) -> dict[str, list[Mapping[str, Any]]]:
    """Merge EventBus replay with recent ticket.action audit records for GUI consumption."""

    buckets: dict[str, list[Mapping[str, Any]]] = {
        "ticket": [],
        "gate": [],
        "health": [],
        "execution": [],
    }

    def _append(channel: str, record: Mapping[str, Any]) -> None:
        buckets[channel].append(record)
        if len(buckets[channel]) > per_channel_limit:
            buckets[channel] = buckets[channel][-per_channel_limit:]

    try:
        for record in event_bus.replay(from_ts=from_ts, to_ts=to_ts):
            channel = _event_channel(record)
            if channel is None:
                continue
            if _is_ticket_action(record):
                _append(channel, _normalize_ticket_action(record))
            else:
                _append(channel, record)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("gui.collect_recent_events.replay_failed", extra={"error": str(exc)})

    if ticket_action_log is not None:
        for action in _load_ticket_actions(ticket_action_log, limit=per_channel_limit):
            _append("ticket", action)

    if fill_placeholders:
        now_iso = datetime.utcnow().isoformat() + "Z"
        for channel in buckets:
            if not buckets[channel]:
                buckets[channel].append(
                    {
                        "ts": now_iso,
                        "event_type": f"{channel}.none",
                        "message": "no recent events available",
                        "source": "placeholder",
                    }
                )

    return buckets


def _event_channel(record: Mapping[str, Any]) -> str | None:
    event_type = str(record.get("event_type") or record.get("record_type") or "").lower()
    if event_type.startswith("ticket"):
        return "ticket"
    if event_type.startswith("gate"):
        return "gate"
    if event_type.startswith("health"):
        return "health"
    if event_type.startswith("execution"):
        return "execution"

    nested_event = str((record.get("event") or {}).get("event", "")).lower()  # type: ignore[call-arg]
    if nested_event.startswith("ticket"):
        return "ticket"
    if nested_event.startswith("gate"):
        return "gate"
    if nested_event.startswith("health"):
        return "health"
    if nested_event.startswith("execution"):
        return "execution"
    return None


def _is_ticket_action(record: Mapping[str, Any]) -> bool:
    event_type = str(record.get("event_type") or record.get("record_type") or "").lower()
    return event_type == "ticket.action"


def _normalize_ticket_action(record: Mapping[str, Any]) -> Mapping[str, Any]:
    guardrails = dict(record.get("guardrails") or {})
    return {
        "ts": record.get("ts"),
        "record_type": "ticket.action",
        "ticket_id": record.get("ticket_id"),
        "action": record.get("action"),
        "actor": record.get("actor"),
        "board_mode": record.get("board_mode"),
        "kill_switch_state": record.get("kill_switch_state") or guardrails.get("kill_switch"),
        "spread_status": record.get("spread_status") or guardrails.get("spread_status"),
        "profit_readiness_status": record.get("profit_readiness_status")
        or guardrails.get("profit_readiness_status"),
        "reduce_only": bool(
            record.get("reduce_only")
            if record.get("reduce_only") is not None
            else guardrails.get("reduce_only", False)
        ),
        "risk_disclosure_state": record.get("risk_disclosure_state")
        or guardrails.get("risk_disclosure"),
        "cfg_hash": record.get("cfg_hash"),
        "data_hash": record.get("data_hash"),
        "consent_reference_id": record.get("consent_reference_id"),
        "auto_execute": bool(record.get("auto_execute", False)),
        "guardrails": guardrails,
        "source": record.get("source", "audit"),
    }


def _load_ticket_actions(path: Path, *, limit: int = 10) -> list[Mapping[str, Any]]:
    if not path.exists():
        return []
    actions: list[Mapping[str, Any]] = []
    try:
        for line in reversed(path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                record = _normalize_ticket_action(json.loads(line))
            except Exception:
                continue
            actions.append(record)
            if len(actions) >= limit:
                break
    except OSError:
        return []
    return list(reversed(actions))


__all__ = [
    "TicketPayloadSerializer",
    "board_get_snapshot",
    "kill_switch_set",
    "collect_recent_events",
]
