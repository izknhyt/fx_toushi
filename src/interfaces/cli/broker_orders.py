"""Stub for `tradectl broker orders` commands."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = [
    "orders_list",
    "orders_show",
    "orders_replay",
    "orders_override",
    "orders_export",
]


def orders_list(*, status: str | None = None, strategy: str | None = None, include_recovery: bool = False) -> list[dict[str, object]]:
    """Stub for listing broker orders."""

    logger.info("cli.broker.orders.list", extra={"status": status, "strategy": strategy, "include_recovery": include_recovery})
    return []


def orders_show(order: str, *, include_history: bool = False, include_evidence: bool = False) -> dict[str, object]:
    """Stub for showing broker order details."""

    logger.info("cli.broker.orders.show", extra={"order": order, "include_history": include_history, "include_evidence": include_evidence})
    return {"order_id": order, "status": "unknown"}


def orders_replay(order: str, *, strict: bool = False, compare_fill_shadow: bool = False) -> None:
    """Stub for replaying broker orders."""

    logger.info("cli.broker.orders.replay", extra={"order": order, "strict": strict, "compare_fill_shadow": compare_fill_shadow})
    return {"status": "ok", "order": order}


def orders_override(order: str, *, action: str, note: str | None = None, runbook_step: str | None = None, assign: str | None = None) -> None:
    """Stub for overriding broker orders."""

    logger.info("cli.broker.orders.override", extra={"order": order, "action": action, "note": note, "runbook_step": runbook_step, "assign": assign})
    return {"status": "ok", "order": order, "action": action}


def orders_export(*, date_from: str, destination: str, fmt: str = "jsonl") -> str:
    """Stub for exporting broker orders."""

    logger.info("cli.broker.orders.export", extra={"from": date_from, "destination": destination, "fmt": fmt})
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("[]", encoding="utf-8")
    return str(dest)
