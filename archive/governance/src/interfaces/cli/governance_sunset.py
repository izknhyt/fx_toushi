"""Governance sunset CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.governance.sunset import StrategySunsetService, SunsetDirective, SunsetPlan


def issue(
    *,
    strategy_id: str,
    reason: str,
    issued_by: str,
    effective_at: str,
    gate_ref: str | None,
    consent_reference_id: str | None,
    dry_run: bool,
    sunset_dir: Path,
) -> Mapping[str, Any]:
    service = StrategySunsetService(sunset_dir=sunset_dir)
    directive = service.issue_directive(
        strategy_id=strategy_id,
        reason=reason,
        issued_by=issued_by,
        effective_at=effective_at,
        gate_ref=gate_ref,
        consent_reference_id=consent_reference_id,
        dry_run=dry_run,
    )
    return {"status": "ok", "directive": directive.to_dict()}


def plan(
    *,
    strategy_id: str,
    directive_id: str | None,
    sunset_dir: Path,
    export_md: Path | None,
) -> Mapping[str, Any]:
    service = StrategySunsetService(sunset_dir=sunset_dir)
    directive = _load_directive(sunset_dir, strategy_id, directive_id)
    plan = service.build_plan(directive)
    if export_md:
        export_md.parent.mkdir(parents=True, exist_ok=True)
        export_md.write_text(_render_plan_md(plan), encoding="utf-8")
    return {"status": "ok", "plan": plan.to_dict(), "export_path": str(export_md) if export_md else None}


def execute(
    *,
    plan_id: str,
    step_id: str,
    executed_by: str,
    evidence_path: Path | None,
    note: str | None,
    sunset_dir: Path,
) -> Mapping[str, Any]:
    service = StrategySunsetService(sunset_dir=sunset_dir)
    log = service.execute_step(
        plan_id,
        step_id=step_id,
        executed_by=executed_by,
        evidence_path=evidence_path,
        note=note,
    )
    return {"status": "ok", "execution": log.to_dict()}


def complete(
    *,
    plan_id: str,
    reallocation_status: str | None,
    sunset_dir: Path,
) -> Mapping[str, Any]:
    service = StrategySunsetService(sunset_dir=sunset_dir)
    receipt = service.complete(plan_id, reallocation_status=reallocation_status)
    return {"status": "ok", "receipt": receipt.to_dict()}


def _render_plan_md(plan: SunsetPlan) -> str:
    lines = [
        f"# Sunset Plan ({plan.plan_id})",
        "",
        f"- Strategy: {plan.strategy_id}",
        f"- Directive: {plan.directive_id}",
        "",
        "## Open Positions",
    ]
    if not plan.open_positions:
        lines.append("- none")
    else:
        for pos in plan.open_positions:
            lines.append(f"- {pos.instrument} {pos.direction} size={pos.size}")
    lines.append("")
    lines.append("## Actions")
    for step in plan.recommended_actions:
        lines.append(f"- {step.step_id}: {step.action} ({step.status})")
    return "\n".join(lines) + "\n"


def _load_directive(
    sunset_dir: Path, strategy_id: str, directive_id: str | None
) -> SunsetDirective:
    strategy_dir = sunset_dir / strategy_id
    if directive_id:
        path = strategy_dir / f"directive_{directive_id}.json"
        if not path.exists():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SunsetDirective(**payload)
    candidates = sorted(strategy_dir.glob("directive_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"directive not found for {strategy_id}")
    payload = json.loads(candidates[-1].read_text(encoding="utf-8"))
    return SunsetDirective(**payload)


__all__ = ["issue", "plan", "execute", "complete"]
