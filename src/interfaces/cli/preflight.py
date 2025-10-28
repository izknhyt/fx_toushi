"""Stub for the `tradectl preflight` checks (see §17.5)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["preflight"]


def preflight(
    profile: str,
    *,
    json_output: bool = False,
    ntp_check: bool = True,
    smtp_check: bool = False,
) -> dict[str, object]:
    """Execute the preflight checklist (stub)."""

    logger.info(
        "cli.preflight.stub",
        extra={
            "profile": profile,
            "json": json_output,
            "ntp_check": ntp_check,
            "smtp_check": smtp_check,
        },
    )
    raise NotImplementedError("tradectl preflight is not implemented in the M1 scaffold")
