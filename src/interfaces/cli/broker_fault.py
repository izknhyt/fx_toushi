"""Stub for `tradectl broker simulate fault` commands."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["simulate_fault", "simulate_list", "simulate_verify"]


def simulate_fault(
    *,
    scenario: str,
    iterations: int = 1,
    auto_stage: bool | None = None,
    attach_evidence: bool = False,
    dry_run: bool = True,
) -> None:
    """Stub for running broker fault simulations."""

    logger.info(
        "cli.broker.simulate.fault.stub",
        extra={
            "scenario": scenario,
            "iterations": iterations,
            "auto_stage": auto_stage,
            "attach_evidence": attach_evidence,
            "dry_run": dry_run,
        },
    )
    raise NotImplementedError("tradectl broker simulate fault is not implemented in the M1 scaffold")


def simulate_list(*, fault_type: str | None = None, json_output: bool = False) -> list[dict[str, object]]:
    """Stub for listing broker fault scenarios."""

    logger.info(
        "cli.broker.simulate.list.stub",
        extra={"fault_type": fault_type, "json": json_output},
    )
    raise NotImplementedError("tradectl broker simulate list is not implemented in the M1 scaffold")


def simulate_verify(
    *,
    scenario: str,
    expected_stage: str | None = None,
    expected_alert: str | None = None,
) -> None:
    """Stub for verifying broker fault expectations."""

    logger.info(
        "cli.broker.simulate.verify.stub",
        extra={"scenario": scenario, "expected_stage": expected_stage, "expected_alert": expected_alert},
    )
    raise NotImplementedError("tradectl broker simulate verify is not implemented in the M1 scaffold")
