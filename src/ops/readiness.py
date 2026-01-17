"""Ops readiness service for scoring and alerting."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.core.health import HealthMonitor
from src.ops_readiness import OpsReadinessEvaluator, OpsReadinessResult

__all__ = ["OpsReadinessService", "OpsReadinessSnapshot"]


@dataclass(slots=True)
class OpsReadinessSnapshot:
    result: OpsReadinessResult
    component_scores: Mapping[str, float]

    def to_payload(self) -> dict[str, object]:
        return {
            "score": self.result.score,
            "status": self.result.status,
            "notes": self.result.notes,
            "evidence": self.result.evidence,
            "missing": self.result.missing,
            "thresholds": dict(self.result.thresholds),
            "runbook_ref": self.result.runbook_ref,
            "generated_at": self.result.generated_at,
            "exit_code": self.result.exit_code,
            "component_scores": dict(self.component_scores),
        }


class OpsReadinessService:
    """Compute ops readiness score, emit metrics, and raise alerts."""

    def __init__(
        self,
        *,
        config_path: Path = Path("config/ops_readiness.yaml"),
        metrics_path: Path = Path("metrics/ops_readiness.jsonl"),
        report_dir: Path = Path("reports/ops/readiness"),
        max_age_days: int = 14,
        event_bus: object | None = None,
        health_monitor: HealthMonitor | None = None,
    ) -> None:
        self._config_path = config_path
        self._metrics_path = metrics_path
        self._report_dir = report_dir
        self._max_age_days = max_age_days
        self._event_bus = event_bus
        self._health_monitor = health_monitor

    def evaluate(self) -> OpsReadinessSnapshot:
        evaluator = OpsReadinessEvaluator(
            config_path=self._config_path,
            max_age_days=self._max_age_days,
        )
        result = evaluator.evaluate()
        component_scores = _component_scores(result.evidence)
        snapshot = OpsReadinessSnapshot(result=result, component_scores=component_scores)
        self._emit_event(
            {
                "event": "ops.readiness.calculated",
                "score": result.score,
                "status": result.status,
                "missing_count": len(result.missing),
            }
        )
        return snapshot

    def record_metrics(self, snapshot: OpsReadinessSnapshot, *, alerts_triggered: int = 0) -> None:
        payload = {
            "ts": _utcnow_iso(),
            "readiness_score": snapshot.result.score,
            "status": snapshot.result.status,
            "component_scores": dict(snapshot.component_scores),
            "alerts_triggered": alerts_triggered,
        }
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def raise_alert(self, snapshot: OpsReadinessSnapshot, *, threshold: int | None = None) -> bool:
        thresholds = snapshot.result.thresholds
        min_score = int(thresholds.get("min_score", 80))
        limit = threshold if threshold is not None else min_score
        if snapshot.result.score >= limit:
            return False
        monitor = self._health_monitor or HealthMonitor()
        runbook = snapshot.result.runbook_ref or "OPS-READINESS-01"
        detail = f"ops_readiness_score={snapshot.result.score} (<{limit})"
        monitor.raise_condition(
            "soft_stop",
            "ops_readiness_low",
            detail=detail,
            recommended_action=f"runbook:{runbook}",
        )
        self._emit_event(
            {
                "event": "ops.readiness.alert",
                "score": snapshot.result.score,
                "status": snapshot.result.status,
                "threshold": limit,
                "runbook_ref": runbook,
            }
        )
        return True

    def generate_report(
        self, snapshot: OpsReadinessSnapshot, *, period: str | None = None
    ) -> Path:
        report_id = period or _week_id()
        path = self._report_dir / f"{report_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = snapshot.to_payload()
        lines = [
            f"# Ops Readiness Report ({report_id})",
            "",
            f"- Generated at: {payload.get('generated_at')}",
            f"- Status: {payload.get('status')}",
            f"- Score: {payload.get('score')}",
            f"- Runbook: {payload.get('runbook_ref')}",
            "",
            "## Missing Evidence",
            "```json",
            json.dumps(payload.get("missing"), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Component Scores",
            "```json",
            json.dumps(payload.get("component_scores"), ensure_ascii=False, indent=2),
            "```",
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _emit_event(self, payload: Mapping[str, object]) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if publish is None:
            return
        try:
            publish(payload, event_type=payload.get("event"))
        except TypeError:
            publish(payload)


def _component_scores(evidence: list[dict[str, object]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for entry in evidence:
        key = entry.get("key")
        if not key:
            continue
        scores[str(key)] = 0.0 if entry.get("issue") else 100.0
    return scores


def _week_id() -> str:
    now = datetime.now(timezone.utc)
    year, week, _ = now.isocalendar()
    return f"{year}{week:02d}"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
