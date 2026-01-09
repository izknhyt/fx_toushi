"""Stub for `tradectl benchmark` commands (see §17.10)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["ingest", "compare", "validate_manual"]


def ingest(
    *,
    provider: str,
    file: str,
    mode: str,
    symbol: str | None = None,
    email: str | None = None,
) -> None:
    """Stub for benchmark ingestion."""

    logger.info(
        "cli.benchmark.ingest.stub",
        extra={"provider": provider, "file": file, "mode": mode, "symbol": symbol, "email": email},
    )
    raise NotImplementedError("tradectl benchmark ingest is not implemented in the M1 scaffold")


def compare(
    *,
    window: str,
    mode: str,
    providers: list[str] | None = None,
    export: str | None = None,
    fail_on_gap: bool = False,
) -> str:
    """Stub for benchmark comparison."""

    logger.info(
        "cli.benchmark.compare.stub",
        extra={
            "window": window,
            "mode": mode,
            "providers": providers or [],
            "export": export,
            "fail_on_gap": fail_on_gap,
        },
    )
    raise NotImplementedError("tradectl benchmark compare is not implemented in the M1 scaffold")


def validate_manual(path: str) -> None:
    """Stub for validating manual benchmark CSV files."""

    logger.info("cli.benchmark.validate_manual.stub", extra={"path": path})
    raise NotImplementedError(
        "tradectl benchmark validate-manual is not implemented in the M1 scaffold"
    )
