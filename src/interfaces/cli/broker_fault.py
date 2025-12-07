"""Stub for `tradectl broker simulate fault` commands."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
import json
from typing import Any, Mapping

from src.brokers.order_lifecycle import OrderLifecycleManager
from src.brokers.stage_guard import AutonomyStageGuard

logger = logging.getLogger(__name__)

__all__ = ["simulate_fault", "simulate_list", "simulate_verify"]


def simulate_fault(
    *,
    scenario: str,
    iterations: int = 1,
    auto_stage: bool | None = None,
    attach_evidence: bool = False,
    dry_run: bool = True,
    metrics_path: Path | None = Path("metrics/broker_faults.jsonl"),
) -> Mapping[str, Any]:
    """Stub for running broker fault simulations."""

    logger.info(
        "cli.broker.simulate.fault",
        extra={"scenario": scenario, "iterations": iterations, "auto_stage": auto_stage, "attach_evidence": attach_evidence, "dry_run": dry_run},
    )
    lifecycle = OrderLifecycleManager()
    guard = AutonomyStageGuard(stage="live")

    code = _scenario_to_code(scenario)
    classification = lifecycle.classify_error(code)
    transition = guard.on_error(classification, actor="system", reason=code)
    recovery: Mapping[str, object] | None = None
    if classification == "circuit_breaker" and (auto_stage or scenario.endswith("_recover")):
        recover_transition = guard.recover(actor="system", reason="circuit_recover")
        if recover_transition:
            recovery = {
                "stage_from": recover_transition.from_stage,
                "stage_to": recover_transition.to_stage,
                "ts": recover_transition.ts.isoformat() + "Z",
            }

    runbook_ref = None
    if classification == "fatal":
        runbook_ref = "RUN-BROKER-AUTH"
    elif classification == "circuit_breaker":
        runbook_ref = "RUN-BROKER-01"

    record = {
        "status": "ok",
        "scenario": scenario,
        "iterations": iterations,
        "dry_run": dry_run,
        "error_code": code,
        "error_class": classification,
        "stage_transition": transition.ts.isoformat() + "Z" if transition else None,
        "stage_from": transition.from_stage if transition else guard.stage,
        "stage_to": transition.to_stage if transition else guard.stage,
        "recovery": recovery,
        "runbook_ref": runbook_ref,
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    if metrics_path:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        sample = {
            "ts": record["ts"],
            "scenario": scenario,
            "error_class": classification,
            "stage_from": record["stage_from"],
            "stage_to": record["stage_to"],
            "recovery": bool(recovery),
            "runbook_ref": runbook_ref,
        }
        try:
            with metrics_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(sample, ensure_ascii=False))
                handle.write("\n")
        except OSError:
            logger.warning("cli.broker.simulate.metrics_write_failed", extra={"path": str(metrics_path)})

    return record


def simulate_list(*, fault_type: str | None = None, json_output: bool = False) -> list[dict[str, object]]:
    """Stub for listing broker fault scenarios."""

    logger.info("cli.broker.simulate.list", extra={"fault_type": fault_type, "json": json_output})
    scenarios = [
        {"name": "timeout", "description": "Provider timeout -> retryable", "class": "retryable"},
        {"name": "429", "description": "Rate limited -> retryable", "class": "retryable"},
        {"name": "auth_failure", "description": "Auth/permission failure -> fatal", "class": "fatal"},
        {"name": "venue_halt", "description": "Venue halt -> circuit_breaker rollback", "class": "circuit_breaker"},
        {"name": "venue_recover", "description": "Venue halt then recover to live", "class": "circuit_breaker"},
    ]
    if fault_type:
        return [s for s in scenarios if s["class"] == fault_type]
    return scenarios


def simulate_verify(
    *,
    scenario: str,
    expected_stage: str | None = None,
    expected_alert: str | None = None,
) -> Mapping[str, Any]:
    """Stub for verifying broker fault expectations."""

    logger.info("cli.broker.simulate.verify", extra={"scenario": scenario, "expected_stage": expected_stage, "expected_alert": expected_alert})
    return {
        "status": "ok",
        "scenario": scenario,
        "expected_stage": expected_stage,
        "expected_alert": expected_alert,
    }


def _scenario_to_code(scenario: str) -> str:
    scenario = scenario.lower()
    if scenario in {"timeout", "http_timeout"}:
        return "timeout"
    if scenario in {"429", "rate_limit", "rate_limit_exceeded"}:
        return "429"
    if scenario in {"venue_halt", "circuit_breaker", "venue_recover"}:
        return "venue_halt"
    return scenario
