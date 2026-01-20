"""Coaching playbook services for trader workflow telemetry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from src.telemetry.trader_workflow import TraderWorkflowTelemetryService, WorkflowSummary

DEFAULT_THRESHOLDS_PATH = Path("config/coaching_thresholds.yaml")
DEFAULT_INSIGHTS_LOG = Path("metrics/coaching_insights.jsonl")
DEFAULT_REPORT_DIR = Path("reports/ops/coaching")
DEFAULT_RUNBOOK_REFS = ["COACHING-01", "RUN-HITL-01"]


@dataclass(slots=True)
class CoachingInsight:
    insight_id: str
    period: str
    bottleneck_metric: str
    value: float
    threshold: float
    status: str
    priority_score: float
    recommendation: str
    runbook_refs: list[str]
    evidence_paths: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "insight_id": self.insight_id,
            "period": self.period,
            "bottleneck_metric": self.bottleneck_metric,
            "value": self.value,
            "threshold": self.threshold,
            "status": self.status,
            "priority_score": self.priority_score,
            "recommendation": self.recommendation,
            "runbook_refs": list(self.runbook_refs),
            "evidence_paths": list(self.evidence_paths),
        }


class CoachingPlaybook:
    """Generate coaching insights from workflow telemetry."""

    def __init__(
        self,
        *,
        telemetry: TraderWorkflowTelemetryService | None = None,
        thresholds_path: Path = DEFAULT_THRESHOLDS_PATH,
        insights_log_path: Path = DEFAULT_INSIGHTS_LOG,
        report_dir: Path = DEFAULT_REPORT_DIR,
    ) -> None:
        self._telemetry = telemetry or TraderWorkflowTelemetryService()
        self._thresholds_path = thresholds_path
        self._insights_log_path = insights_log_path
        self._report_dir = report_dir

    def summary(self, *, window: timedelta, export_md: Path | None = None) -> dict[str, object]:
        summary = self._telemetry.summarize(window=window)
        record = self._telemetry.record_summary(summary)
        result = {"status": summary.status, "summary": summary.to_dict(), "record": record}
        if export_md:
            export_md.parent.mkdir(parents=True, exist_ok=True)
            export_md.write_text(_render_summary_md(summary), encoding="utf-8")
            result["export_path"] = str(export_md)
        return result

    def create_insights(
        self,
        *,
        window: timedelta,
        threshold_path: Path | None = None,
        export_md: Path | None = None,
        dry_run: bool = False,
        tag: str | None = None,
    ) -> dict[str, object]:
        summary = self._telemetry.summarize(window=window)
        thresholds = _load_thresholds(threshold_path or self._thresholds_path)
        insights = _build_insights(summary, thresholds, tag=tag)
        if not dry_run:
            for insight in insights:
                self._append_insight(insight)
        if export_md:
            export_md.parent.mkdir(parents=True, exist_ok=True)
            export_md.write_text(_render_insights_md(summary, insights), encoding="utf-8")
        return {
            "status": "ok",
            "summary": summary.to_dict(),
            "insights": [insight.to_dict() for insight in insights],
            "export_path": str(export_md) if export_md else None,
        }

    def review(
        self,
        *,
        week: str,
        diff: bool = False,
        export_md: Path | None = None,
    ) -> dict[str, object]:
        insights = _load_insights(self._insights_log_path, period=week)
        payload: dict[str, object] = {
            "status": "ok",
            "week": week,
            "insights": insights,
        }
        if diff:
            payload["diff"] = _compare_weeks(self._insights_log_path, week)
        if export_md:
            export_md.parent.mkdir(parents=True, exist_ok=True)
            export_md.write_text(_render_review_md(week, insights, payload.get("diff")), encoding="utf-8")
            payload["export_path"] = str(export_md)
        return payload

    def simulate(self, *, scenario: str, window: timedelta) -> dict[str, object]:
        summary = self._telemetry.summarize(window=window)
        return {
            "status": "ok",
            "scenario": scenario,
            "summary": summary.to_dict(),
            "note": "simulation_stub",
        }

    def _append_insight(self, insight: CoachingInsight) -> None:
        payload = {
            "schema_version": "coaching.insight.v1",
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
                "+00:00", "Z"
            ),
            **insight.to_dict(),
            "due_date": _next_wednesday().isoformat(),
        }
        self._insights_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._insights_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _load_thresholds(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    thresholds = payload.get("thresholds") if isinstance(payload, dict) else None
    if not isinstance(thresholds, dict):
        return {}
    parsed: dict[str, float] = {}
    for key, value in thresholds.items():
        try:
            parsed[key] = float(value)
        except (TypeError, ValueError):
            continue
    return parsed


def _build_insights(
    summary: WorkflowSummary,
    thresholds: dict[str, float],
    *,
    tag: str | None = None,
) -> list[CoachingInsight]:
    period = _current_week()
    insights: list[CoachingInsight] = []
    mapping = [
        (
            "avg_approval_latency_sec",
            summary.avg_approval_latency_sec,
            thresholds.get("avg_approval_latency_sec", 45.0),
            "max",
            "Review approval latency and queue handling.",
        ),
        (
            "checklist_completion_rate",
            summary.checklist_completion_rate,
            thresholds.get("checklist_completion_rate_min", 0.95),
            "min",
            "Reinforce checklist adherence and simplify steps.",
        ),
        (
            "guarded_time_ratio",
            summary.guarded_time_ratio,
            thresholds.get("guarded_time_ratio_max", 0.2),
            "max",
            "Reduce guarded-mode dwell time via runbook tuning.",
        ),
        (
            "mistake_rate",
            summary.mistake_rate,
            thresholds.get("mistake_rate_max", 0.05),
            "max",
            "Review recent mistakes and update training materials.",
        ),
    ]
    for metric, value, threshold, direction, recommendation in mapping:
        if value is None:
            continue
        status = "ok"
        priority = 0.0
        if direction == "max" and value > threshold:
            status = "over_threshold"
            priority = _priority_score_max(value, threshold)
        if direction == "min" and value < threshold:
            status = "over_threshold"
            priority = _priority_score_min(value, threshold)
        if status != "over_threshold" and tag is None:
            continue
        insight_id = f"COACH-{metric.upper()}-{period}"
        if tag:
            insight_id = f"{insight_id}-{tag}"
        insights.append(
            CoachingInsight(
                insight_id=insight_id,
                period=period,
                bottleneck_metric=metric,
                value=float(value),
                threshold=float(threshold),
                status=status,
                priority_score=priority,
                recommendation=recommendation,
                runbook_refs=list(DEFAULT_RUNBOOK_REFS),
                evidence_paths=[],
            )
        )
    return insights


def _load_insights(path: Path, *, period: str) -> list[dict[str, object]]:
    if not path.exists():
        return []
    insights: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("period") != period:
            continue
        insights.append(data)
    return insights


def _compare_weeks(path: Path, week: str) -> dict[str, object]:
    if not path.exists():
        return {"status": "no_data"}
    target = _load_insights(path, period=week)
    year, week_num = _split_week(week)
    prev_week = date.fromisocalendar(year, week_num, 1) - timedelta(days=7)
    prev_period = prev_week.strftime("%G-W%V")
    previous = _load_insights(path, period=prev_period)
    return {
        "previous_week": prev_period,
        "current_count": len(target),
        "previous_count": len(previous),
    }


def _render_summary_md(summary: WorkflowSummary) -> str:
    lines = [
        "# Trader Workflow Summary",
        "",
        f"- Window start: {summary.window_start}",
        f"- Window end: {summary.window_end}",
        f"- Status: {summary.status}",
        "",
        "## KPIs",
        f"- avg_approval_latency_sec: {summary.avg_approval_latency_sec}",
        f"- checklist_completion_rate: {summary.checklist_completion_rate}",
        f"- guarded_time_ratio: {summary.guarded_time_ratio}",
        f"- mistake_rate: {summary.mistake_rate}",
    ]
    return "\n".join(lines) + "\n"


def _render_insights_md(summary: WorkflowSummary, insights: Iterable[CoachingInsight]) -> str:
    lines = [
        "# Coaching Insights",
        "",
        f"Status: {summary.status}",
        f"Window: {summary.window_start} -> {summary.window_end}",
        "",
        "| Insight | Metric | Value | Threshold | Priority | Recommendation |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for insight in insights:
        lines.append(
            "| {insight_id} | {metric} | {value:.2f} | {threshold:.2f} | {priority:.2f} | {rec} |".format(
                insight_id=insight.insight_id,
                metric=insight.bottleneck_metric,
                value=insight.value,
                threshold=insight.threshold,
                priority=insight.priority_score,
                rec=insight.recommendation,
            )
        )
    return "\n".join(lines) + "\n"


def _render_review_md(
    week: str,
    insights: Iterable[dict[str, object]],
    diff: dict[str, object] | None,
) -> str:
    lines = [
        f"# Coaching Review {week}",
        "",
        "| Insight | Metric | Status | Priority |",
        "| --- | --- | --- | --- |",
    ]
    for insight in insights:
        lines.append(
            "| {id} | {metric} | {status} | {priority} |".format(
                id=insight.get("insight_id"),
                metric=insight.get("bottleneck_metric"),
                status=insight.get("status"),
                priority=insight.get("priority_score"),
            )
        )
    if diff:
        lines.extend(["", "## Diff", f"- Previous week: {diff.get('previous_week')}"])
        lines.append(f"- Current count: {diff.get('current_count')}")
        lines.append(f"- Previous count: {diff.get('previous_count')}")
    return "\n".join(lines) + "\n"


def _priority_score_max(value: float, threshold: float) -> float:
    if threshold <= 0:
        return 1.0
    return max(0.0, min(1.0, (value - threshold) / threshold))


def _priority_score_min(value: float, threshold: float) -> float:
    if threshold <= 0:
        return 1.0
    return max(0.0, min(1.0, (threshold - value) / threshold))


def _current_week() -> str:
    return date.today().strftime("%G-W%V")


def _split_week(week: str) -> tuple[int, int]:
    year_str, week_str = week.split("-W", 1)
    return int(year_str), int(week_str)


def _next_wednesday() -> date:
    today = date.today()
    days_ahead = (2 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


__all__ = ["CoachingInsight", "CoachingPlaybook"]
