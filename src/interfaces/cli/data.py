"""Stubs for `tradectl data` subcommands (see §17.6)."""

from __future__ import annotations

import logging
from typing import Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "status",
    "failover",
    "manual_template",
    "validate_csv",
    "jobs",
    "manual_report",
    "hash_path",
]


def status(
    *,
    providers: Sequence[str] | None = None,
    watch: bool = False,
    log_stage_eval: bool = False,
) -> None:
    """Stub for data status monitoring."""

    logger.info(
        "cli.data.status.stub",
        extra={"providers": list(providers or ()), "watch": watch, "log_stage_eval": log_stage_eval},
    )
    raise NotImplementedError("tradectl data status is not implemented in the M1 scaffold")


def failover(
    target: str,
    *,
    mode: str | None = None,
    log_stage_change: bool = False,
) -> None:
    """Stub for triggering a manual failover."""

    logger.info(
        "cli.data.failover.stub",
        extra={"target": target, "mode": mode, "log_stage_change": log_stage_change},
    )
    raise NotImplementedError("tradectl data failover is not implemented in the M1 scaffold")


def manual_template(provider: str, symbol: str, date: str, *, timeframe: str) -> str:
    """Stub for generating twin CSV templates."""

    logger.info(
        "cli.data.manual_template.stub",
        extra={"provider": provider, "symbol": symbol, "date": date, "timeframe": timeframe},
    )
    raise NotImplementedError("tradectl data manual-template is not implemented in the M1 scaffold")


def validate_csv(path: str) -> None:
    """Stub for validating manual CSV submissions."""

    logger.info("cli.data.validate_csv.stub", extra={"path": path})
    raise NotImplementedError("tradectl data validate-csv is not implemented in the M1 scaffold")


def jobs(*, pending: bool = False, export_json: bool = False) -> list[dict[str, object]]:
    """Stub for listing manual ingestion jobs."""

    logger.info("cli.data.jobs.stub", extra={"pending": pending, "export_json": export_json})
    raise NotImplementedError("tradectl data jobs is not implemented in the M1 scaffold")


def manual_report(
    *,
    date: str,
    provider: str | None = None,
    symbol: str | None = None,
    attach: bool = False,
) -> str:
    """Stub for generating manual ingestion reports."""

    logger.info(
        "cli.data.manual_report.stub",
        extra={"date": date, "provider": provider, "symbol": symbol, "attach": attach},
    )
    raise NotImplementedError("tradectl data manual-report is not implemented in the M1 scaffold")


def hash_path(path: str) -> str:
    """Stub for computing twin CSV hashes."""

    logger.info("cli.data.hash.stub", extra={"path": path})
    raise NotImplementedError("tradectl data hash is not implemented in the M1 scaffold")
