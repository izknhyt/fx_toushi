"""Stub scaffolding for `tradectl broker` subcommands (see §80.5)."""

from __future__ import annotations

import logging

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

    logger.info(
        "cli.broker.shadow_start.stub",
        extra={"scenario": scenario, "strict": strict},
    )
    raise NotImplementedError("tradectl broker shadow start is not implemented in the M1 scaffold")


def shadow_status(*, alerts: bool = False) -> dict[str, object]:
    """Stub for reporting broker shadow status."""

    logger.info("cli.broker.shadow_status.stub", extra={"alerts": alerts})
    raise NotImplementedError("tradectl broker shadow status is not implemented in the M1 scaffold")


def shadow_export(*, date: str, destination: str | None = None) -> str:
    """Stub for exporting broker shadow evidence."""

    logger.info(
        "cli.broker.shadow_export.stub",
        extra={"date": date, "destination": destination},
    )
    raise NotImplementedError("tradectl broker shadow export is not implemented in the M1 scaffold")


def monitor_status(*, alerts: bool = False) -> dict[str, object]:
    """Stub for broker monitor status."""

    logger.info("cli.broker.monitor_status.stub", extra={"alerts": alerts})
    raise NotImplementedError("tradectl broker monitor status is not implemented in the M1 scaffold")


def monitor_test(*, adapter: str) -> None:
    """Stub for broker monitor test command."""

    logger.info("cli.broker.monitor_test.stub", extra={"adapter": adapter})
    raise NotImplementedError("tradectl broker monitor test is not implemented in the M1 scaffold")


def monitor_limit(*, burst: int | None = None, sustained: int | None = None) -> None:
    """Stub for adjusting broker rate limits."""

    logger.info(
        "cli.broker.monitor_limit.stub",
        extra={"burst": burst, "sustained": sustained},
    )
    raise NotImplementedError("tradectl broker monitor limit is not implemented in the M1 scaffold")
