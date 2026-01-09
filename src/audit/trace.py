"""Audit trace helpers for AC-06."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

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
    filtered = [
        entry
        for entry in entries
        if entry.get("ticket_id") == order_id or entry.get("order_id") == order_id
    ]
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
    kill_switch_state: str,
    spread_status: str,
    profit_readiness_status: str,
    reduce_only: bool,
    risk_disclosure_state: str,
    cfg_hash: str,
    data_hash: str,
    auto_execute: bool = False,
    guardrails: Mapping[str, object] | None = None,
    spread_state: Mapping[str, object] | None = None,
    health_state: str = "ok",
    latency_data_status: str = "ok",
    slippage_data_status: str = "ok",
    delta: Mapping[str, object] | None = None,
    consent_reference_id: str | None = None,
    notes: str | None = None,
    path: Path = DEFAULT_TICKET_ACTION_LOG,
) -> Mapping[str, object]:
    """Append a ticket.action audit entry including auto_execute flag."""

    guardrails_payload = dict(guardrails or {})
    guardrails_payload.setdefault("kill_switch", kill_switch_state)
    guardrails_payload.setdefault("spread_status", spread_status)
    guardrails_payload.setdefault("reduce_only", reduce_only)
    guardrails_payload.setdefault("health_state", health_state)
    guardrails_payload.setdefault("profit_readiness_status", profit_readiness_status)

    record: dict[str, object] = {
        "ts": _now(),
        "record_type": "ticket.action",
        "schema_version": "ticket.action.v2",
        "ticket_id": ticket_id,
        "action": action,
        "actor": actor,
        "board_mode": board_mode,
        "kill_switch_state": kill_switch_state,
        "spread_status": spread_status,
        "profit_readiness_status": profit_readiness_status,
        "reduce_only": bool(reduce_only),
        "risk_disclosure_state": risk_disclosure_state,
        "auto_execute": bool(auto_execute),
        "guardrails": guardrails_payload,
        "spread_state": spread_state or {},
        "health_state": health_state,
        "cfg_hash": cfg_hash,
        "data_hash": data_hash,
        "latency_data_status": latency_data_status,
        "slippage_data_status": slippage_data_status,
        "delta": delta or {"before": {}, "after": {}, "diff": {}, "decision": action},
        "consent_reference_id": consent_reference_id,
    }
    if notes:
        record["notes"] = notes
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
    logger.info(
        "audit.ticket_action.logged", extra={"ticket_id": ticket_id, "auto_execute": auto_execute}
    )
    return record
