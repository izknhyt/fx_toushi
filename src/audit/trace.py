"""Audit trace helpers for AC-06."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_LOG = Path("logs/audit/hitl.jsonl")


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
