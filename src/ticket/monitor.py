"""Ticket monitor scaffolding for AC-02 HITL workflows."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_EVENT_LOG_PATH = Path("logs/events/ticket.oco_ack.jsonl")
DEFAULT_EXPORT_PATH = Path("reports/performance/paper/sample_orders.parquet")


@dataclass(slots=True)
class TicketMonitorResult:
    """Structured payload returned by :func:`monitor_ticket`."""

    ticket_id: str
    mode: str
    watch_seconds: int
    latency_ms: int
    acknowledged: bool
    acked_at: str
    events_log: str
    export_path: str | None

    def to_mapping(self) -> Mapping[str, object]:
        return asdict(self)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _append_event(path: Path, payload: Mapping[str, object]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _write_sample_orders(path: Path, *, ticket_id: str, mode: str, ack_ts: datetime, latency_ms: int) -> None:
    _ensure_parent(path)
    df = pd.DataFrame(
        [
            {
                "ticket_id": ticket_id,
                "mode": mode,
                "symbol": "USDJPY",
                "status": "oco_acknowledged",
                "oco_ack_latency_ms": latency_ms,
                "created_at": (ack_ts - timedelta(milliseconds=latency_ms)).isoformat().replace("+00:00", "Z"),
                "acknowledged_at": ack_ts.isoformat().replace("+00:00", "Z"),
            }
        ]
    )
    df.to_parquet(path)


def monitor_ticket(
    *,
    ticket_id: str | None = None,
    mode: str = "paper",
    watch_seconds: int = 120,
    export_path: Path | None = DEFAULT_EXPORT_PATH,
    event_log_path: Path = DEFAULT_EVENT_LOG_PATH,
) -> TicketMonitorResult:
    """Simulate monitoring a ticket until an `oco_ack` event arrives."""

    effective_ticket_id = ticket_id or f"TKT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    watch_seconds = max(watch_seconds, 1)
    latency_ms = min(int(watch_seconds * 1000 * 0.7), watch_seconds * 1000)
    ack_ts = datetime.now(timezone.utc)
    ack_payload = {
        "event": "ticket.oco_ack",
        "ticket_id": effective_ticket_id,
        "mode": mode,
        "latency_ms": latency_ms,
        "ack_timestamp": ack_ts.isoformat().replace("+00:00", "Z"),
    }
    _append_event(event_log_path, ack_payload)

    export_str: str | None = None
    if export_path is not None:
        _write_sample_orders(export_path, ticket_id=effective_ticket_id, mode=mode, ack_ts=ack_ts, latency_ms=latency_ms)
        export_str = str(export_path)

    result = TicketMonitorResult(
        ticket_id=effective_ticket_id,
        mode=mode,
        watch_seconds=watch_seconds,
        latency_ms=latency_ms,
        acknowledged=True,
        acked_at=ack_payload["ack_timestamp"],
        events_log=str(event_log_path),
        export_path=export_str,
    )
    logger.info("ticket.monitor.completed", extra=result.to_mapping())
    return result


__all__ = [
    "TicketMonitorResult",
    "monitor_ticket",
    "DEFAULT_EVENT_LOG_PATH",
    "DEFAULT_EXPORT_PATH",
]
