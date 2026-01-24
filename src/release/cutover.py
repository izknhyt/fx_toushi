"""Broker cutover checklist generation and verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.brokers.certification import load_result
from src.brokers.monitor import BrokerSloConfig
from src.compliance import RiskDisclosureService

DEFAULT_BASE_DIR = Path("reports/audit/release")
DEFAULT_CERT_ROOT = Path("evidence/broker_certification")
DEFAULT_SHADOW_METRICS = Path("metrics/broker_shadow.jsonl")
DEFAULT_RATE_LIMIT_METRICS = Path("metrics/broker_rate_limit.jsonl")
DEFAULT_RUNBOOK_DRILL_DIR = Path("reports/ops/runbook_drill")
DEFAULT_SLO_PATH = Path("config/brokers/slo.yaml")


@dataclass(frozen=True)
class CutoverItem:
    item_id: str
    label: str
    status: str
    evidence_path: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "label": self.label,
            "status": self.status,
            "evidence_path": self.evidence_path,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class CutoverChecklist:
    profile: str
    generated_at: str
    items: tuple[CutoverItem, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "generated_at": self.generated_at,
            "items": [item.to_dict() for item in self.items],
        }


class CutoverChecklistService:
    def __init__(
        self,
        *,
        base_dir: Path = DEFAULT_BASE_DIR,
        certification_root: Path = DEFAULT_CERT_ROOT,
        shadow_metrics_path: Path = DEFAULT_SHADOW_METRICS,
        rate_limit_metrics_path: Path = DEFAULT_RATE_LIMIT_METRICS,
        runbook_drill_dir: Path = DEFAULT_RUNBOOK_DRILL_DIR,
        slo_path: Path = DEFAULT_SLO_PATH,
    ) -> None:
        self._base_dir = base_dir
        self._cert_root = certification_root
        self._shadow_metrics_path = shadow_metrics_path
        self._rate_limit_metrics_path = rate_limit_metrics_path
        self._runbook_drill_dir = runbook_drill_dir
        self._slo_path = slo_path

    def generate(self, *, profile: str, version: str | None = None) -> CutoverChecklist:
        items = [
            self._check_certification(),
            self._check_shadow_dry_run(),
            self._check_rate_limit(),
            self._check_runbook_drill(),
            self._check_risk_disclosure(),
        ]
        checklist = CutoverChecklist(
            profile=profile,
            generated_at=_utcnow_iso(),
            items=tuple(items),
        )
        self._write(checklist, version=version)
        return checklist

    def verify(self, *, profile: str, version: str | None = None) -> dict[str, object]:
        checklist = self.generate(profile=profile, version=version)
        pending = [item for item in checklist.items if item.status != "done"]
        return {
            "status": "ok" if not pending else "blocked",
            "profile": checklist.profile,
            "pending": [item.to_dict() for item in pending],
        }

    def _write(self, checklist: CutoverChecklist, *, version: str | None) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"{version}_broker_cutover_" if version else "broker_cutover_"
        json_path = self._base_dir / f"{prefix}{checklist.profile}.json"
        md_path = self._base_dir / f"{prefix}{checklist.profile}.md"
        json_path.write_text(
            json.dumps(checklist.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        md_path.write_text(self._render_markdown(checklist), encoding="utf-8")

    def _render_markdown(self, checklist: CutoverChecklist) -> str:
        lines = [
            f"# Broker Cutover Checklist ({checklist.profile})",
            "",
            f"- generated_at: {checklist.generated_at}",
            "",
        ]
        for item in checklist.items:
            mark = "x" if item.status == "done" else " "
            evidence = f" (evidence: {item.evidence_path})" if item.evidence_path else ""
            note = f" — {item.notes}" if item.notes else ""
            lines.append(f"- [{mark}] {item.label} [{item.item_id}] status={item.status}{evidence}{note}")
        return "\n".join(lines) + "\n"

    def _check_certification(self) -> CutoverItem:
        result_path = _latest_result(self._cert_root)
        if not result_path:
            return CutoverItem("API-01", "BrokerCertificationSuite completed", "pending")
        result = load_result(result_path)
        status = "done" if result.overall_status in {"pass", "pass_with_warning"} else "blocked"
        return CutoverItem(
            "API-01",
            "BrokerCertificationSuite completed",
            status,
            evidence_path=str(result_path),
            notes=result.overall_status,
        )

    def _check_shadow_dry_run(self) -> CutoverItem:
        payload = _load_last_jsonl(self._shadow_metrics_path)
        if not payload:
            return CutoverItem("API-02", "FillShadow 24h dry run", "pending")
        pending = int(payload.get("pending", 0))
        alerts = int(payload.get("alerts", payload.get("drift_count", 0)))
        status = "done" if pending == 0 and alerts == 0 else "blocked"
        return CutoverItem(
            "API-02",
            "FillShadow 24h dry run",
            status,
            evidence_path=str(self._shadow_metrics_path),
            notes=f"pending={pending} alerts={alerts}",
        )

    def _check_rate_limit(self) -> CutoverItem:
        payloads = list(_iter_jsonl(self._rate_limit_metrics_path))
        if not payloads:
            return CutoverItem("API-03", "Rate limit stage stable", "pending")
        slo = BrokerSloConfig.from_path(self._slo_path)
        breaches = [
            p
            for p in payloads
            if p.get("queue_wait_ms") is not None
            and float(p.get("queue_wait_ms")) > slo.queue_warn_sec * 1000
        ]
        status = "done" if not breaches else "blocked"
        notes = f"queue_breaches={len(breaches)}"
        return CutoverItem(
            "API-03",
            "Rate limit stage stable",
            status,
            evidence_path=str(self._rate_limit_metrics_path),
            notes=notes,
        )

    def _check_runbook_drill(self) -> CutoverItem:
        if not self._runbook_drill_dir.exists():
            return CutoverItem("API-04", "Runbook drills completed", "pending")
        matches = [
            path
            for path in self._runbook_drill_dir.glob("*.md")
            if "broker" in path.name
        ]
        status = "done" if matches else "pending"
        evidence = str(matches[-1]) if matches else None
        return CutoverItem("API-04", "Runbook drills completed", status, evidence)

    def _check_risk_disclosure(self) -> CutoverItem:
        state = RiskDisclosureService().fetch_state()
        status = "done" if state.status == "active" else "blocked"
        notes = f"status={state.status}"
        return CutoverItem("API-05", "Risk disclosure active", status, notes=notes)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _latest_result(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = sorted(root.glob("*/result.json"))
    return candidates[-1] if candidates else None


def _load_last_jsonl(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    latest: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            latest = json.loads(line)
        except json.JSONDecodeError:
            continue
    return latest


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


__all__ = ["CutoverChecklist", "CutoverChecklistService", "CutoverItem"]
