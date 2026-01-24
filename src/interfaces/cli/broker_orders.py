"""CLI helpers for broker order lifecycle reporting."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Iterable

from src.brokers.order_lifecycle import OrderLifecycleManager
from src.brokers.order_store import OrderStateStore

logger = logging.getLogger(__name__)

__all__ = [
    "orders_list",
    "orders_show",
    "orders_override",
    "orders_export",
    "orders_replay",
]


def orders_list(
    *,
    mode: str = "paper",
    status: Iterable[str] | None = None,
    strategy_id: str | None = None,
    include_recovery: bool = False,
    store: OrderStateStore | None = None,
) -> dict[str, object]:
    store = store or OrderStateStore()
    items = []
    for envelope, state in store.list(mode=mode, status_in=status, strategy_id=strategy_id):
        payload = {
            "order_id": state.order_id,
            "status": state.status,
            "last_transition": state.last_transition,
            "attempt": state.attempt,
            "evidence_hash": state.evidence_hash,
            "stage_guard_stage": envelope.stage_guard_stage if envelope else None,
            "ticket_id": envelope.ticket_id if envelope else None,
            "strategy_id": envelope.strategy_id if envelope else None,
        }
        if include_recovery:
            payload["recovery_plan"] = state.recovery_plan.to_dict() if state.recovery_plan else None
        items.append(payload)
    logger.info("cli.broker.orders.list", extra={"mode": mode, "count": len(items)})
    return {"status": "ok", "mode": mode, "orders": items, "schema_version": "broker.orders.v1"}


def orders_show(
    *,
    order_id: str,
    mode: str = "paper",
    include_history: bool = False,
    store: OrderStateStore | None = None,
) -> dict[str, object]:
    store = store or OrderStateStore()
    envelope, state = store.load(order_id, mode=mode)
    if state is None:
        return {"status": "missing", "order_id": order_id}
    payload: dict[str, object] = {
        "status": "ok",
        "order_id": order_id,
        "mode": mode,
        "envelope": envelope.to_dict() if envelope else None,
        "state": state.to_dict(),
    }
    if include_history:
        payload["history"] = [entry.to_dict() for entry in store.history(order_id, mode=mode)]
    logger.info("cli.broker.orders.show", extra={"order_id": order_id, "mode": mode})
    return payload


def orders_override(
    *,
    order_id: str,
    action: str,
    mode: str = "paper",
    note: str | None = None,
    runbook_step: str | None = None,
    assign: str | None = None,
    store: OrderStateStore | None = None,
) -> dict[str, object]:
    store = store or OrderStateStore()
    envelope, state = store.load(order_id, mode=mode)
    if state is None:
        return {"status": "missing", "order_id": order_id}
    plan = state.recovery_plan
    if plan is None:
        return {"status": "no_recovery_plan", "order_id": order_id}
    if assign:
        plan.assigned_to = assign
    if note:
        plan.notes.append(note)
    if runbook_step:
        plan.notes.append(f"runbook_step={runbook_step}")
    if action == "abort":
        plan.status = "aborted"
    elif action == "retry":
        plan.status = "in_progress"
    elif action == "manual":
        plan.status = "in_progress"
        plan.notes.append("manual_override")
    plan.updated_at = _utcnow_iso()

    lifecycle = OrderLifecycleManager(store=store)
    lifecycle.update_state(
        order_id,
        status=state.status,
        mode=mode,
        payload={"recovery_plan": plan, "runbook_ref": plan.runbook_ref},
    )
    logger.info(
        "cli.broker.orders.override",
        extra={"order_id": order_id, "action": action, "mode": mode},
    )
    return {"status": "ok", "order_id": order_id, "action": action, "plan": plan.to_dict()}


def orders_replay(
    *,
    order_id: str,
    mode: str = "paper",
    compare_fill_shadow: bool = False,
    store: OrderStateStore | None = None,
) -> dict[str, object]:
    store = store or OrderStateStore()
    _, state = store.load(order_id, mode=mode)
    if state is None:
        return {"status": "missing", "order_id": order_id}
    payload = {
        "status": "ok",
        "order_id": order_id,
        "mode": mode,
        "fill_summary": state.fill_summary,
    }
    if compare_fill_shadow:
        payload["fill_shadow_match"] = bool(state.fill_summary)
    logger.info("cli.broker.orders.replay", extra={"order_id": order_id, "mode": mode})
    return payload


def orders_export(
    *,
    mode: str = "paper",
    dest: Path,
    fmt: str = "jsonl",
    store: OrderStateStore | None = None,
) -> dict[str, object]:
    store = store or OrderStateStore()
    dest.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for envelope, state in store.list(mode=mode):
        rows.append(
            {
                "order_id": state.order_id,
                "status": state.status,
                "attempt": state.attempt,
                "last_transition": state.last_transition,
                "evidence_hash": state.evidence_hash,
                "stage_guard_stage": envelope.stage_guard_stage if envelope else None,
                "ticket_id": envelope.ticket_id if envelope else None,
            }
        )
    if fmt == "csv":
        with dest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else [])
            if rows:
                writer.writeheader()
                writer.writerows(rows)
    else:
        with dest.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False))
                handle.write("\n")
    logger.info("cli.broker.orders.export", extra={"mode": mode, "dest": str(dest)})
    return {"status": "ok", "path": str(dest), "count": len(rows)}


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
