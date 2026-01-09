"""Stub scaffolding for `tradectl broker` subcommands (see §80.5)."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "shadow_start",
    "shadow_status",
    "shadow_export",
    "monitor_status",
    "monitor_test",
    "monitor_limit",
]


def shadow_start(*, scenario: str | None = None, strict: bool = False) -> None:
    """Stub for starting broker shadow capture."""

    logger.info("cli.broker.shadow_start", extra={"scenario": scenario, "strict": strict})
    return {"status": "ok", "scenario": scenario, "strict": strict}


def shadow_status(*, alerts: bool = False) -> dict[str, object]:
    """Stub for reporting broker shadow status."""

    logger.info("cli.broker.shadow_status", extra={"alerts": alerts})
    return {"status": "ok", "alerts": alerts, "sessions": []}


def shadow_export(*, date: str, destination: str | None = None) -> str:
    """Stub for exporting broker shadow evidence."""

    logger.info("cli.broker.shadow_export", extra={"date": date, "destination": destination})
    dest = destination or f"logs/broker/shadow_{date}.jsonl"
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text("[]", encoding="utf-8")
    return dest


def monitor_status(*, alerts: bool = False) -> dict[str, object]:
    """Stub for broker monitor status."""

    logger.info("cli.broker.monitor_status", extra={"alerts": alerts})
    return {"status": "ok", "alerts": alerts, "stage": "live_shadow"}


def monitor_test(*, adapter: str) -> None:
    """Stub for broker monitor test command."""

    logger.info("cli.broker.monitor_test", extra={"adapter": adapter})
    return {"status": "ok", "adapter": adapter}


def monitor_limit(*, burst: int | None = None, sustained: int | None = None) -> None:
    """Stub for adjusting broker rate limits."""

    logger.info("cli.broker.monitor_limit", extra={"burst": burst, "sustained": sustained})
    return {"status": "ok", "burst": burst, "sustained": sustained}
