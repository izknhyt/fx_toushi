"""Stub for `tradectl broker simulate fault` commands."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from src.diagnostics.broker.api_fault_lab import ApiFaultInjectionLab

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
    """Run broker fault simulations via the API fault lab."""

    logger.info(
        "cli.broker.simulate.fault",
        extra={
            "scenario": scenario,
            "iterations": iterations,
            "auto_stage": auto_stage,
            "attach_evidence": attach_evidence,
            "dry_run": dry_run,
        },
    )
    lab = ApiFaultInjectionLab()
    result = lab.run(scenario, iterations=iterations, auto_stage=bool(auto_stage), dry_run=dry_run)
    record = {
        "status": "ok",
        "scenario": scenario,
        "iterations": iterations,
        "dry_run": dry_run,
        "stage_guard_action": result.stage_guard_action,
        "recovery_plan_id": result.recovery_plan_id,
        "report_path": result.report_path,
        "ops_todo_created": result.ops_todo_created,
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    if metrics_path:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        retryable = str(scenario) in {"429", "rate_limit_exhaust"}
        sample = {
            "ts": record["ts"],
            "scenario": scenario,
            "stage_guard_action": record.get("stage_guard_action"),
            "recovery_plan": bool(record.get("recovery_plan_id")),
            "ops_todo_created": record.get("ops_todo_created"),
            "retryable": retryable,
        }
        try:
            with metrics_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(sample, ensure_ascii=False))
                handle.write("\n")
        except OSError:
            logger.warning(
                "cli.broker.simulate.metrics_write_failed", extra={"path": str(metrics_path)}
            )

    return record


def simulate_list(
    *, fault_type: str | None = None, json_output: bool = False
) -> list[dict[str, object]]:
    """List available API fault scenarios."""

    logger.info("cli.broker.simulate.list", extra={"fault_type": fault_type, "json": json_output})
    lab = ApiFaultInjectionLab()
    scenarios = [
        {
            "name": scenario.scenario_id,
            "description": scenario.description,
            "fault_type": scenario.fault_type,
        }
        for scenario in lab.list_scenarios()
    ]
    if fault_type:
        return [s for s in scenarios if s["fault_type"] == fault_type]
    return scenarios


def simulate_verify(
    *,
    scenario: str,
    expected_stage: str | None = None,
    expected_alert: str | None = None,
) -> Mapping[str, Any]:
    """Stub for verifying broker fault expectations."""

    logger.info(
        "cli.broker.simulate.verify",
        extra={
            "scenario": scenario,
            "expected_stage": expected_stage,
            "expected_alert": expected_alert,
        },
    )
    return {
        "status": "ok",
        "scenario": scenario,
        "expected_stage": expected_stage,
        "expected_alert": expected_alert,
    }
