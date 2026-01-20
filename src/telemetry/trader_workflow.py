"""Telemetry collection for trader workflow coaching loops."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_WORKFLOW_METRICS = Path("metrics/trader_workflow.jsonl")


@dataclass(slots=True)
class WorkflowEvent:
    ts: datetime
    event_type: str
    ticket_id: str | None
    actor: str | None
    board_mode: str | None
    payload: dict[str, Any]


@dataclass(slots=True)
class WorkflowSummary:
    status: str
    window_start: str
    window_end: str
    sample_count: int
    avg_approval_latency_sec: float | None
    checklist_completion_rate: float | None
    guarded_time_ratio: float | None
    mistake_rate: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "sample_count": self.sample_count,
            "avg_approval_latency_sec": self.avg_approval_latency_sec,
            "checklist_completion_rate": self.checklist_completion_rate,
            "guarded_time_ratio": self.guarded_time_ratio,
            "mistake_rate": self.mistake_rate,
        }


class TraderWorkflowTelemetryService:
    """Collect and aggregate HITL workflow telemetry."""

    def __init__(self, *, metrics_path: Path = DEFAULT_WORKFLOW_METRICS) -> None:
        self._metrics_path = metrics_path

    def record_event(
        self,
        *,
        event_type: str,
        ticket_id: str | None = None,
        actor: str | None = None,
        board_mode: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        ts = datetime.now(timezone.utc).replace(microsecond=0)
        record = {
            "schema_version": "trader.workflow.v1",
            "event": event_type,
            "ts": ts.isoformat().replace("+00:00", "Z"),
            "ticket_id": ticket_id,
            "actor": actor,
            "board_mode": board_mode,
            "payload": payload or {},
        }
        self._append_jsonl(record)
        return record

    def summarize(self, *, window: timedelta) -> WorkflowSummary:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        start = now - window
        events = self._load_events(start, now)
        summary = WorkflowSummary(
            status="ok" if events else "no_data",
            window_start=start.isoformat().replace("+00:00", "Z"),
            window_end=now.isoformat().replace("+00:00", "Z"),
            sample_count=len(events),
            avg_approval_latency_sec=_avg_approval_latency(events),
            checklist_completion_rate=_checklist_completion_rate(events),
            guarded_time_ratio=_guarded_time_ratio(events),
            mistake_rate=_mistake_rate(events),
        )
        return summary

    def record_summary(self, summary: WorkflowSummary) -> dict[str, object]:
        record = {
            "schema_version": "trader.workflow.summary.v1",
            "event": "trader_workflow.summary",
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
                "+00:00", "Z"
            ),
            **summary.to_dict(),
        }
        self._append_jsonl(record)
        return record

    def _load_events(self, start: datetime, end: datetime) -> list[WorkflowEvent]:
        if not self._metrics_path.exists():
            return []
        events: list[WorkflowEvent] = []
        for line in self._metrics_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("event") == "trader_workflow.summary":
                continue
            ts = _parse_ts(data.get("ts"))
            if ts is None or ts < start or ts > end:
                continue
            events.append(
                WorkflowEvent(
                    ts=ts,
                    event_type=str(data.get("event")),
                    ticket_id=data.get("ticket_id"),
                    actor=data.get("actor"),
                    board_mode=data.get("board_mode"),
                    payload=data.get("payload") if isinstance(data.get("payload"), dict) else {},
                )
            )
        return events

    def _append_jsonl(self, payload: dict[str, object]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")


def _avg_approval_latency(events: list[WorkflowEvent]) -> float | None:
    proposals: dict[str, datetime] = {}
    approvals: list[float] = []
    for event in events:
        if not event.ticket_id:
            continue
        if event.event_type in {"ticket.proposed", "ticket.created"}:
            proposals[event.ticket_id] = event.ts
        if event.event_type in {"ticket.approved", "ticket.ack"}:
            start = proposals.get(event.ticket_id)
            if start:
                approvals.append((event.ts - start).total_seconds())
    if not approvals:
        return None
    return sum(approvals) / len(approvals)


def _checklist_completion_rate(events: list[WorkflowEvent]) -> float | None:
    completed = sum(1 for event in events if event.event_type == "checklist.completed")
    missed = sum(1 for event in events if event.event_type == "checklist.missed")
    total = completed + missed
    if total == 0:
        return None
    return completed / total


def _guarded_time_ratio(events: list[WorkflowEvent]) -> float | None:
    if not events:
        return None
    guarded = sum(1 for event in events if event.board_mode == "guarded")
    return guarded / len(events)


def _mistake_rate(events: list[WorkflowEvent]) -> float | None:
    mistakes = sum(1 for event in events if event.event_type == "workflow.mistake")
    if not events:
        return None
    return mistakes / len(events)


def _parse_ts(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


__all__ = ["TraderWorkflowTelemetryService", "WorkflowEvent", "WorkflowSummary"]
