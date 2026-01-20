"""Shadow session orchestration for shadow state updates."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from src.core.event_bus import EventBus
from src.shadow.store import ShadowStateStore


@dataclass(slots=True)
class ShadowEvent:
    event_type: str
    payload: dict[str, Any]
    received_at: str


class ShadowSessionOrchestrator:
    """Route event bus payloads into the ShadowStateStore."""

    def __init__(
        self,
        *,
        event_bus: EventBus | None,
        store: ShadowStateStore | None = None,
        event_log: Path = Path("logs/events/shadow_session.jsonl"),
    ) -> None:
        self._event_bus = event_bus
        self._store = store or ShadowStateStore()
        self._event_log = event_log
        self._event_log.parent.mkdir(parents=True, exist_ok=True)
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self, *, event_types: list[str]) -> None:
        if self._event_bus is None:
            raise RuntimeError("event_bus is required to start the shadow session")
        for event_type in event_types:
            iterator = await self._event_bus.subscribe(event_type)
            task = asyncio.create_task(self._drain(iterator, event_type))
            self._tasks.append(task)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks = []

    def process_event(self, event_type: str, payload: dict[str, Any]) -> ShadowEvent:
        if event_type in {"ticket.proposed", "ticket.updated"}:
            ticket_id = str(payload.get("ticket_id") or payload.get("id") or "unknown")
            status = str(payload.get("status") or "pending")
            self._store.upsert_ticket(ticket_id, status=status, payload=payload)
        elif event_type.startswith("health.") or event_type.startswith("ops."):
            alert_id = str(payload.get("alert_id") or payload.get("id") or _event_id(event_type))
            self._store.add_alert(alert_id, event_type=event_type, payload=payload)
        elif event_type == "shadow.ack":
            ack_id = str(payload.get("ack_id") or _event_id(event_type))
            source = str(payload.get("source") or "shadow")
            reference_id = str(payload.get("reference_id") or payload.get("ticket_id") or "unknown")
            actor = payload.get("actor")
            self._store.record_ack(ack_id, source=source, reference_id=reference_id, actor=actor)
        record = ShadowEvent(
            event_type=event_type,
            payload=payload,
            received_at=_utcnow_iso(),
        )
        self._append_event(record)
        return record

    async def _drain(self, iterator: Any, event_type: str) -> None:
        async for payload in iterator:
            if isinstance(payload, dict):
                self.process_event(event_type, payload)

    def _append_event(self, event: ShadowEvent) -> None:
        with self._event_log.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "ts": event.received_at,
                        "event_type": event.event_type,
                        "payload": event.payload,
                    },
                    ensure_ascii=False,
                )
            )
            handle.write("\n")


def _event_id(event_type: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{event_type.replace('.', '_')}_{ts}"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["ShadowEvent", "ShadowSessionOrchestrator"]
