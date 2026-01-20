"""Compliance regression runner for stop/freeze and capital guard checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.worklog import OpsWorklogEntry, OpsWorklogService
from src.risk.capital_guard import CapitalAllocationGuard, CapitalGuardSnapshot
from tools.compliance_ticket_generator import BrokerSymbolRule, TicketScenario, _load_broker_rules

DEFAULT_RULES = Path("config/broker_rules.yaml")
DEFAULT_OUTPUT_DIR = Path("reports/compliance/regression")
DEFAULT_METRICS_PATH = Path("metrics/compliance_regression.json")
DEFAULT_AUDIT_LOG = Path("logs/audit/compliance_regression.jsonl")


@dataclass(slots=True)
class RegressionResult:
    profile: str
    tickets_tested: int
    min_distance_violations: int
    freeze_level_violations: int
    rounding_issues: int
    throttle_triggered: bool
    proposal_drop_pct: float
    cooldown_recovered_minutes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "compliance.regression.v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
                "+00:00", "Z"
            ),
            "profile": self.profile,
            "tickets_tested": self.tickets_tested,
            "min_distance_violations": self.min_distance_violations,
            "freeze_level_violations": self.freeze_level_violations,
            "rounding_issues": self.rounding_issues,
            "throttle_triggered": self.throttle_triggered,
            "proposal_drop_pct": round(self.proposal_drop_pct, 2),
            "cooldown_recovered_minutes": self.cooldown_recovered_minutes,
        }


def load_scenarios(path: Path) -> list[TicketScenario]:
    if not path.exists():
        return []
    scenarios: list[TicketScenario] = []
    files = [path] if path.is_file() else sorted(path.glob("*.jsonl"))
    for file_path in files:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            scenarios.append(
                TicketScenario(
                    scenario_id=str(payload.get("scenario_id")),
                    pair=str(payload.get("pair")),
                    mode=str(payload.get("mode")),
                    timestamp=str(payload.get("timestamp")),
                    spread_pips=float(payload.get("spread_pips", 0.0)),
                    atr_pips=float(payload.get("atr_pips", 0.0)),
                    proposed_sl_pips=float(payload.get("proposed_sl_pips", 0.0)),
                    proposed_tp_pips=float(payload.get("proposed_tp_pips", 0.0)),
                    lot=float(payload.get("lot", 0.0)),
                    reason_tags=list(payload.get("reason_tags") or []),
                    adjustments=dict(payload.get("adjustments") or {}),
                )
            )
    return scenarios


def run_regression(
    *,
    profile: str,
    scenarios_path: Path,
    rules_path: Path = DEFAULT_RULES,
    capitalsim: str = "baseline",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    audit_log: Path = DEFAULT_AUDIT_LOG,
    dry_run: bool = False,
    actor: str | None = None,
) -> dict[str, object]:
    rules = _load_broker_rules(rules_path)
    scenarios = load_scenarios(scenarios_path)
    result = _evaluate(scenarios, rules, profile=profile, capitalsim=capitalsim)
    report_paths = _write_reports(result, output_dir=output_dir, metrics_path=metrics_path, dry_run=dry_run)
    _append_audit(
        audit_log,
        {
            "event": "audit.compliance_regression",
            "profile": profile,
            "tickets_tested": result.tickets_tested,
            "violations": {
                "min_distance": result.min_distance_violations,
                "freeze_level": result.freeze_level_violations,
                "rounding": result.rounding_issues,
            },
            "throttle_triggered": result.throttle_triggered,
            "artifact_paths": report_paths,
            "actor": actor,
        },
        dry_run=dry_run,
    )
    if not dry_run:
        _record_worklog(actor, result)
    return {
        "status": "ok",
        "result": result.to_dict(),
        "report_path": report_paths.get("markdown"),
        "metrics_path": report_paths.get("metrics"),
    }


def diff_regression(
    *,
    current: Path,
    against: Path,
    threshold: float = 0.02,
) -> dict[str, object]:
    current_payload = _load_metrics(current)
    against_payload = _load_metrics(against)
    if not current_payload or not against_payload:
        return {"status": "error", "reason": "missing_metrics"}
    delta = {
        "proposal_drop_pct": current_payload.get("proposal_drop_pct", 0)
        - against_payload.get("proposal_drop_pct", 0),
        "min_distance_violations": current_payload.get("min_distance_violations", 0)
        - against_payload.get("min_distance_violations", 0),
    }
    status = "ok"
    if abs(float(delta["proposal_drop_pct"])) > threshold:
        status = "threshold_exceeded"
    return {"status": status, "delta": delta, "current": current_payload, "against": against_payload}


def _evaluate(
    scenarios: list[TicketScenario],
    rules: dict[str, BrokerSymbolRule],
    *,
    profile: str,
    capitalsim: str,
) -> RegressionResult:
    min_distance_violations = 0
    freeze_level_violations = 0
    rounding_issues = 0
    throttle_triggered = False
    throttle_count = 0

    guard = CapitalAllocationGuard()
    for idx, scenario in enumerate(scenarios):
        rule = rules.get(scenario.pair)
        if not rule:
            continue
        min_distance = rule.min_distance_pips.get("stop_loss", 0.0)
        if scenario.proposed_sl_pips < min_distance or scenario.proposed_tp_pips < min_distance:
            min_distance_violations += 1
        if rule.freeze_level_pips and (
            scenario.proposed_sl_pips < rule.freeze_level_pips
            or scenario.proposed_tp_pips < rule.freeze_level_pips
        ):
            freeze_level_violations += 1
        if not _aligned_lot(scenario.lot, rule.lot_step, rule.min_lot):
            rounding_issues += 1
        margin_peak = 0.65
        if capitalsim == "stress" and idx % 2 == 0:
            margin_peak = 0.95
        decision = guard.simulate(CapitalGuardSnapshot(margin_utilization_peak=margin_peak))
        if decision in {"throttle", "halt"}:
            throttle_triggered = True
            throttle_count += 1

    tickets_tested = len(scenarios)
    violations = min_distance_violations + freeze_level_violations + rounding_issues
    proposal_drop_pct = (violations + throttle_count) / tickets_tested if tickets_tested else 0.0
    cooldown_minutes = 180 if capitalsim == "stress" else 90
    return RegressionResult(
        profile=profile,
        tickets_tested=tickets_tested,
        min_distance_violations=min_distance_violations,
        freeze_level_violations=freeze_level_violations,
        rounding_issues=rounding_issues,
        throttle_triggered=throttle_triggered,
        proposal_drop_pct=proposal_drop_pct,
        cooldown_recovered_minutes=cooldown_minutes,
    )


def _write_reports(
    result: RegressionResult,
    *,
    output_dir: Path,
    metrics_path: Path,
    dry_run: bool,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    date_stamp = date.today().strftime("%Y%m%d")
    markdown_path = output_dir / f"regression_{date_stamp}.md"
    metrics_out = output_dir / f"regression_{date_stamp}.json"
    payload = result.to_dict()
    if not dry_run:
        markdown_path.write_text(_render_markdown(payload), encoding="utf-8")
        metrics_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"markdown": str(markdown_path), "metrics": str(metrics_path), "metrics_snapshot": str(metrics_out)}


def _render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Compliance Regression Report",
        "",
        f"- Generated at: {payload.get('generated_at')}",
        f"- Profile: {payload.get('profile')}",
        "",
        "## Summary",
        f"- Tickets tested: {payload.get('tickets_tested')}",
        f"- Min distance violations: {payload.get('min_distance_violations')}",
        f"- Freeze level violations: {payload.get('freeze_level_violations')}",
        f"- Rounding issues: {payload.get('rounding_issues')}",
        f"- Proposal drop pct: {payload.get('proposal_drop_pct')}",
        f"- Cooldown recovered minutes: {payload.get('cooldown_recovered_minutes')}",
        "",
    ]
    return "\n".join(lines) + "\n"


def _append_audit(path: Path, payload: dict[str, object], *, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        **payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False))
        handle.write("\n")


def _record_worklog(actor: str | None, result: RegressionResult) -> None:
    service = OpsWorklogService()
    entry = OpsWorklogEntry(
        schema_version="ops.worklog.v1",
        ts=datetime.now(timezone.utc),
        task="compliance_regression",
        duration_min=45,
        owner=actor or "ops",
        mode=result.profile,
        source="cli",
        related_artifacts=["metrics/compliance_regression.json"],
        health_state="ok",
        board_mode="normal",
        notes=f"violations={result.min_distance_violations + result.freeze_level_violations}",
    )
    service.record(entry)


def _aligned_lot(lot: float, step: float, min_lot: float) -> bool:
    if lot < min_lot:
        return False
    if step <= 0:
        return True
    multiple = round(lot / step)
    return abs(multiple * step - lot) < 1e-6


def _load_metrics(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


__all__ = ["run_regression", "diff_regression", "load_scenarios", "RegressionResult"]
