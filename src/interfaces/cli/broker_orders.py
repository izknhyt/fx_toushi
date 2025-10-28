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

    logger.info(
        "cli.broker.orders.list.stub",
        extra={"status": status, "strategy": strategy, "include_recovery": include_recovery},
    )
    raise NotImplementedError("tradectl broker orders list is not implemented in the M1 scaffold")


def orders_show(order: str, *, include_history: bool = False, include_evidence: bool = False) -> dict[str, object]:
    """Stub for showing broker order details."""

    logger.info(
        "cli.broker.orders.show.stub",
        extra={"order": order, "include_history": include_history, "include_evidence": include_evidence},
    )
    raise NotImplementedError("tradectl broker orders show is not implemented in the M1 scaffold")


def orders_replay(order: str, *, strict: bool = False, compare_fill_shadow: bool = False) -> None:
    """Stub for replaying broker orders."""

    logger.info(
        "cli.broker.orders.replay.stub",
        extra={"order": order, "strict": strict, "compare_fill_shadow": compare_fill_shadow},
    )
    raise NotImplementedError("tradectl broker orders replay is not implemented in the M1 scaffold")


def orders_override(order: str, *, action: str, note: str | None = None, runbook_step: str | None = None, assign: str | None = None) -> None:
    """Stub for overriding broker orders."""

    logger.info(
        "cli.broker.orders.override.stub",
        extra={
            "order": order,
            "action": action,
            "note": note,
            "runbook_step": runbook_step,
            "assign": assign,
        },
    )
    raise NotImplementedError("tradectl broker orders override is not implemented in the M1 scaffold")


def orders_export(*, date_from: str, destination: str, fmt: str = "jsonl") -> str:
    """Stub for exporting broker orders."""

    logger.info(
        "cli.broker.orders.export.stub",
        extra={"from": date_from, "destination": destination, "fmt": fmt},
    )
    raise NotImplementedError("tradectl broker orders export is not implemented in the M1 scaffold")
