"""Research promotion workflow helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.research.pipeline import GateEvaluationResult, ResearchPipelineService, ValidationResult

DEFAULT_PROMOTION_DIR = Path("reports") / "research" / "promotion"
DEFAULT_EVENT_LOG = Path("logs") / "events" / "research_promotion.jsonl"
DEFAULT_AUDIT_LOG = Path("logs") / "audit" / "research_promotion.jsonl"


class PromotionError(RuntimeError):
    """Raised when promotion evaluation fails."""


@dataclass(slots=True)
class PromotionResult:
    strategy_id: str
    target_stage: str
    status: str
    gate: GateEvaluationResult
    validation: ValidationResult | None
    checklist_path: Path | None
    report_path: Path | None
    dry_run_path: Path | None

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "target_stage": self.target_stage,
            "status": self.status,
            "gate": self.gate.to_dict(),
            "validation": self.validation.to_dict() if self.validation else None,
            "checklist_path": str(self.checklist_path) if self.checklist_path else None,
            "report_path": str(self.report_path) if self.report_path else None,
            "dry_run_path": str(self.dry_run_path) if self.dry_run_path else None,
        }


def promote(
    *,
    strategy_id: str,
    target_stage: str,
    window: str,
    mode: str,
    suite_path: Path,
    metrics_path: Path | None,
    note: str | None,
    attachments: list[Path],
    dry_run: bool,
    output_dir: Path = DEFAULT_PROMOTION_DIR,
    event_log: Path = DEFAULT_EVENT_LOG,
    audit_log: Path = DEFAULT_AUDIT_LOG,
) -> PromotionResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    service = ResearchPipelineService(suite_path=suite_path)
    validation = service.run_validation(
        strategy_id=strategy_id,
        window=window,
        mode=mode,
        metrics_path=metrics_path,
    )
    gate = service.evaluate_gate(validation)
    status = "pass" if gate.status == "pass" else "blocked"

    date_stamp = _date_stamp()
    checklist_path = output_dir / f"{strategy_id}_{date_stamp}_checklist.md"
    dry_run_path = (
        output_dir / f"{strategy_id}_{date_stamp}_dryrun.json" if dry_run else None
    )
    report_path = None if dry_run else output_dir / f"{strategy_id}_{date_stamp}.md"

    _write_checklist(
        checklist_path,
        strategy_id=strategy_id,
        target_stage=target_stage,
        gate=gate,
        validation=validation,
        attachments=attachments,
        note=note,
    )
    if dry_run_path:
        dry_run_path.write_text(
            json.dumps(
                {
                    "strategy_id": strategy_id,
                    "target_stage": target_stage,
                    "status": status,
                    "gate": gate.to_dict(),
                    "validation": validation.to_dict(),
                    "attachments": [str(p) for p in attachments],
                    "note": note,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    if report_path:
        _write_report(
            report_path,
            strategy_id=strategy_id,
            target_stage=target_stage,
            status=status,
            gate=gate,
            validation=validation,
            attachments=attachments,
            note=note,
        )

    _append_event(
        event_log,
        {
            "event": "research.promotion",
            "ts": _utcnow_iso(),
            "strategy_id": strategy_id,
            "target_stage": target_stage,
            "status": status,
            "dry_run": dry_run,
            "gate": gate.to_dict(),
            "validation_status": validation.status,
            "checklist_path": str(checklist_path),
            "report_path": str(report_path) if report_path else None,
        },
    )
    _append_event(
        audit_log,
        {
            "event": "audit.research_promotion",
            "ts": _utcnow_iso(),
            "strategy_id": strategy_id,
            "target_stage": target_stage,
            "status": status,
            "dry_run": dry_run,
            "note": note,
            "attachments": [str(p) for p in attachments],
            "validation_status": validation.status,
        },
    )

    return PromotionResult(
        strategy_id=strategy_id,
        target_stage=target_stage,
        status=status,
        gate=gate,
        validation=validation,
        checklist_path=checklist_path,
        report_path=report_path,
        dry_run_path=dry_run_path,
    )


def _write_checklist(
    path: Path,
    *,
    strategy_id: str,
    target_stage: str,
    gate: GateEvaluationResult,
    validation: ValidationResult,
    attachments: list[Path],
    note: str | None,
) -> None:
    lines = [
        f"# Promotion Checklist ({strategy_id})",
        "",
        f"- Target: {target_stage}",
        f"- Gate: {gate.status}",
        f"- Validation: {validation.status}",
        "",
        "## Evidence",
    ]
    if attachments:
        lines.extend([f"- {path}" for path in attachments])
    else:
        lines.append("- (none)")
    if gate.reasons:
        lines.append("")
        lines.append("## Gate Failures")
        lines.extend([f"- {reason}" for reason in gate.reasons])
    if note:
        lines.append("")
        lines.append("## Notes")
        lines.append(note)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(
    path: Path,
    *,
    strategy_id: str,
    target_stage: str,
    status: str,
    gate: GateEvaluationResult,
    validation: ValidationResult,
    attachments: list[Path],
    note: str | None,
) -> None:
    lines = [
        f"# Promotion Result ({strategy_id})",
        "",
        f"- Target: {target_stage}",
        f"- Status: {status}",
        f"- Validation: {validation.status}",
        f"- Gate: {gate.status}",
        "",
        "## Attachments",
    ]
    if attachments:
        lines.extend([f"- {path}" for path in attachments])
    else:
        lines.append("- (none)")
    if note:
        lines.append("")
        lines.append("## Notes")
        lines.append(note)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_event(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _date_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


__all__ = ["PromotionResult", "PromotionError", "promote"]
