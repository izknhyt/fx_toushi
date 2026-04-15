"""Shared GUI/shadow surface helpers for shadow feedback recovery execution state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

DEFAULT_SHADOW_FEEDBACK_RECOVERY_LEDGER = Path("logs/ops/shadow_feedback_recovery.jsonl")


def summarize_shadow_feedback_recovery_execution(
    recovery_packet: Mapping[str, Any] | None,
    ledger_path: Path = DEFAULT_SHADOW_FEEDBACK_RECOVERY_LEDGER,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    packet = dict(recovery_packet or {})
    rows: list[dict[str, Any]] = []
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, Mapping) and str(payload.get("event") or "") == "shadow.feedback.recovery":
                rows.append(dict(payload))

    rows.sort(key=lambda item: str(item.get("ts") or ""))
    recent = rows[-limit:] if limit > 0 else rows
    latest = dict(rows[-1]) if rows else {}

    summary: dict[str, int] = {}
    for row in rows:
        action = str(row.get("recovery_action") or "unknown")
        summary[action] = summary.get(action, 0) + 1

    packet_status = str(packet.get("status") or "unknown")
    packet_action = str(packet.get("recovery_action") or "continue_shadow")
    latest_action = str(latest.get("recovery_action") or "")
    latest_matches_packet = bool(latest) and latest_action == packet_action

    if packet_status == "ready":
        if latest_matches_packet:
            resolution_status = "executed_pending_clear"
            recommended_action = "complete_recovery_checklist"
            should_alert = True
        else:
            resolution_status = "pending_execution"
            recommended_action = "execute_recovery_packet"
            should_alert = True
    elif packet_status == "not_required":
        if latest:
            resolution_status = "resolved"
            recommended_action = "continue_shadow"
            should_alert = False
        else:
            resolution_status = "not_required"
            recommended_action = "continue_shadow"
            should_alert = False
    else:
        resolution_status = "unknown"
        recommended_action = "review_recovery_state"
        should_alert = False

    return {
        "status": "ok",
        "count": len(rows),
        "summary": summary,
        "latest": latest,
        "recent": recent[-5:],
        "ledger_path": str(ledger_path),
        "packet_status": packet_status,
        "packet_action": packet_action,
        "latest_action": latest_action,
        "latest_matches_packet": latest_matches_packet,
        "resolution_status": resolution_status,
        "recommended_action": recommended_action,
        "should_alert": should_alert,
    }


__all__ = [
    "DEFAULT_SHADOW_FEEDBACK_RECOVERY_LEDGER",
    "summarize_shadow_feedback_recovery_execution",
]
