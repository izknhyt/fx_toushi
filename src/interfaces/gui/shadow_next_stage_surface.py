"""Shared GUI/shadow surface helpers for shadow next-stage execution state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER = Path("logs/ops/shadow_next_stage_execution.jsonl")


def summarize_shadow_next_stage_execution(
    ledger_path: Path = DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    if not ledger_path.exists():
        return {
            "status": "ok",
            "count": 0,
            "summary": {},
            "latest": {},
            "recent": [],
            "ledger_path": str(ledger_path),
        }

    rows: list[dict[str, Any]] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping) and str(payload.get("event") or "") == "shadow.next_stage.execution":
            rows.append(dict(payload))

    rows.sort(key=lambda item: str(item.get("ts") or ""))
    recent = rows[-limit:] if limit > 0 else rows
    latest = dict(rows[-1]) if rows else {}

    summary: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        summary[status] = summary.get(status, 0) + 1

    return {
        "status": "ok",
        "count": len(rows),
        "summary": summary,
        "latest": latest,
        "recent": recent[-5:],
        "ledger_path": str(ledger_path),
    }


__all__ = ["DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER", "summarize_shadow_next_stage_execution"]
