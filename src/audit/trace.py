"""Audit trace helpers for AC-06."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_LOG = Path("logs/audit/hitl.jsonl")
DEFAULT_TICKET_ACTION_LOG = Path("logs/audit/ticket_action.jsonl")


@dataclass(slots=True)
class AuditTrace:
    order_id: str
    entries: list[Mapping[str, object]]
    log_path: str
    export_path: str | None

    def to_mapping(self) -> Mapping[str, object]:
        return asdict(self)


def _load_entries(log_path: Path) -> list[Mapping[str, object]]:
    if not log_path.exists():
        return []
    entries: list[Mapping[str, object]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("audit.trace.invalid_json", extra={"line": line[:64]})
    return entries


def _write_markdown(trace: AuditTrace, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Audit Trace for {trace.order_id}",
        "",
        f"- Source: {trace.log_path}",
        f"- Entries: {len(trace.entries)}",
        "",
        "| ts | event | payload |",
        "| --- | --- | --- |",
    ]
    for entry in trace.entries:
        ts = entry.get("ts") or entry.get("timestamp") or "n/a"
        event = entry.get("event") or entry.get("type") or "unknown"
        payload = {k: v for k, v in entry.items() if k not in {"ts", "timestamp", "event", "type"}}
        lines.append(f"| {ts} | {event} | `{json.dumps(payload, ensure_ascii=False)}` |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def trace_order(
    *,
    order_id: str,
    log_path: Path = DEFAULT_AUDIT_LOG,
    export_path: Path | None = None,
) -> AuditTrace:
    entries = _load_entries(log_path)
    filtered = [entry for entry in entries if entry.get("ticket_id") == order_id or entry.get("order_id") == order_id]
    trace = AuditTrace(
        order_id=order_id,
        entries=filtered,
        log_path=str(log_path),
        export_path=str(export_path) if export_path else None,
    )
    if export_path is not None:
        _write_markdown(trace, export_path)
    logger.info(
        "audit.trace.generated",
        extra={"order_id": order_id, "count": len(filtered), "export": trace.export_path},
    )
    return trace


__all__ = ["trace_order", "AuditTrace", "DEFAULT_AUDIT_LOG"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_ticket_action(
    *,
    ticket_id: str,
    action: str,
    actor: str,
    board_mode: str,
    auto_execute: bool,
    spread_state: Mapping[str, object] | None,
    health_state: str,
    cfg_hash: str,
    data_hash: str,
    profit_readiness_status: str,
    latency_data_status: str,
    slippage_data_status: str,
    delta: Mapping[str, object],
    notes: str | None = None,
    path: Path = DEFAULT_TICKET_ACTION_LOG,
) -> Mapping[str, object]:
    """Append a ticket.action audit entry including auto_execute flag."""

    record: dict[str, object] = {
        "ts": _now(),
        "record_type": "ticket.action",
        "ticket_id": ticket_id,
        "action": action,
        "actor": actor,
        "board_mode": board_mode,
        "auto_execute": bool(auto_execute),
        "spread_state": spread_state or {},
        "health_state": health_state,
        "cfg_hash": cfg_hash,
        "data_hash": data_hash,
        "profit_readiness_status": profit_readiness_status,
        "latency_data_status": latency_data_status,
        "slippage_data_status": slippage_data_status,
        "delta": delta,
    }
    if notes:
        record["notes"] = notes
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
    logger.info("audit.ticket_action.logged", extra={"ticket_id": ticket_id, "auto_execute": auto_execute})
    return record
