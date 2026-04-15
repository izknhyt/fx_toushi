"""Ops health dashboard aggregation service (FR-48)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.core.event_bus import EventBus
from src.core.gate import GateState
from src.journal import TradeJournalService

DEFAULT_HEALTH_STATE = Path("snapshots/latest/health_state.json")
DEFAULT_KILL_SWITCH_STATE = Path("snapshots/latest/kill_switch_state.json")
DEFAULT_GATE_STATE = Path("snapshots/latest/gate_state.json")
DEFAULT_BENCHMARK_GAP_LOG = Path("logs/events/benchmark_gap.jsonl")
DEFAULT_METRICS_PATH = Path("metrics/ops_dashboard.jsonl")
DEFAULT_WORKFLOW_METRICS = Path("metrics/trader_workflow.jsonl")
DEFAULT_COACHING_INSIGHTS = Path("metrics/coaching_insights.jsonl")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_last_jsonl(path: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return None
    for raw in reversed(lines):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    return None


def _read_last_event(path: Path, event_name: str) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return None
    for raw in reversed(lines):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == event_name:
            return payload
    return None


def _summarize_coaching_insights(path: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return None
    total = 0
    over_threshold = 0
    last_ts = None
    for raw in lines:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        total += 1
        if payload.get("status") == "over_threshold":
            over_threshold += 1
        last_ts = payload.get("ts") or last_ts
    return {
        "total": total,
        "over_threshold": over_threshold,
        "last_ts": last_ts,
    }


def _read_recent_diagnostics(path: Path, *, limit: int = 2) -> list[list[str]]:
    if not path.exists():
        return []
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return []
    recent = []
    for raw in lines[-limit:]:
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            continue
        diagnostics = record.get("diagnostics_raw", record.get("diagnostics"))
        if isinstance(diagnostics, list):
            recent.append([str(item) for item in diagnostics])
    return recent


def _filter_diagnostics(
    diagnostics: list[str], recent: list[list[str]], *, missing_threshold: int = 3
) -> list[str]:
    if not diagnostics:
        return []
    filtered: list[str] = []
    for code in diagnostics:
        if not code.endswith("_missing"):
            filtered.append(code)
            continue
        if len(recent) >= missing_threshold - 1 and all(code in entry for entry in recent):
            filtered.append(code)
    return filtered


@dataclass(slots=True)
class OpsHealthDashboard:
    status: str
    generated_at: str
    health: Mapping[str, Any] | None
    kill_switch: Mapping[str, Any] | None
    gate_state: Mapping[str, Any] | None
    benchmark_gap: Mapping[str, Any] | None
    journal_highlights: list[Mapping[str, Any]]
    workflow_summary: Mapping[str, Any] | None
    coaching_insights: Mapping[str, Any] | None
    diagnostics: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "health": self.health,
            "kill_switch": self.kill_switch,
            "gate_state": self.gate_state,
            "benchmark_gap": self.benchmark_gap,
            "journal_highlights": list(self.journal_highlights),
            "workflow_summary": self.workflow_summary,
            "coaching_insights": self.coaching_insights,
            "diagnostics": list(self.diagnostics),
        }


class OpsHealthDashboardService:
    """Aggregate guardrail/ops signals into a dashboard payload."""

    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        health_state_path: Path = DEFAULT_HEALTH_STATE,
        kill_switch_state_path: Path = DEFAULT_KILL_SWITCH_STATE,
        gate_state_path: Path = DEFAULT_GATE_STATE,
        benchmark_gap_log: Path = DEFAULT_BENCHMARK_GAP_LOG,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        journal_path: Path | str = "logs/journal/journal_entries.db",
        workflow_metrics_path: Path = DEFAULT_WORKFLOW_METRICS,
        coaching_insights_path: Path = DEFAULT_COACHING_INSIGHTS,
    ) -> None:
        self._event_bus = event_bus
        self._health_state_path = health_state_path
        self._kill_switch_state_path = kill_switch_state_path
        self._gate_state_path = gate_state_path
        self._benchmark_gap_log = benchmark_gap_log
        self._metrics_path = metrics_path
        self._journal_path = journal_path
        self._workflow_metrics_path = workflow_metrics_path
        self._coaching_insights_path = coaching_insights_path

    def build(self) -> OpsHealthDashboard:
        diagnostics: list[str] = []
        health = _read_json(self._health_state_path)
        if health is None:
            diagnostics.append("health_state_missing")
        kill_switch = _read_json(self._kill_switch_state_path)
        if kill_switch is None:
            diagnostics.append("kill_switch_state_missing")
        gate_state = None
        if self._gate_state_path.exists():
            try:
                gate_state = GateState.load(self._gate_state_path).to_dict()
            except Exception:
                diagnostics.append("gate_state_invalid")
                gate_state = None
        else:
            diagnostics.append("gate_state_missing")

        benchmark_gap = _read_last_jsonl(self._benchmark_gap_log)
        if benchmark_gap is None:
            diagnostics.append("benchmark_gap_missing")

        journal_service = TradeJournalService(path=self._journal_path)
        entries = journal_service.list()
        journal_highlights = list(entries[-3:]) if entries else []
        if not journal_highlights:
            diagnostics.append("journal_missing")

        workflow_summary = _read_last_event(self._workflow_metrics_path, "trader_workflow.summary")
        coaching_insights = _summarize_coaching_insights(self._coaching_insights_path)

        raw_diagnostics = list(diagnostics)
        recent = _read_recent_diagnostics(self._metrics_path, limit=2)
        diagnostics = _filter_diagnostics(raw_diagnostics, recent)
        status = "ok" if not diagnostics else "degraded"
        payload = OpsHealthDashboard(
            status=status,
            generated_at=_utcnow_iso(),
            health=health,
            kill_switch=kill_switch,
            gate_state=gate_state,
            benchmark_gap=benchmark_gap,
            journal_highlights=journal_highlights,
            workflow_summary=workflow_summary,
            coaching_insights=coaching_insights,
            diagnostics=diagnostics,
        )
        self._append_metrics(payload, raw_diagnostics=raw_diagnostics)
        self._emit_event(payload)
        return payload

    def _append_metrics(self, payload: OpsHealthDashboard, *, raw_diagnostics: list[str]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": payload.generated_at,
            "event": "ops.dashboard",
            "status": payload.status,
            "diagnostics": payload.diagnostics,
            "diagnostics_raw": list(raw_diagnostics),
        }
        with self._metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    def _emit_event(self, payload: OpsHealthDashboard) -> None:
        if self._event_bus is None:
            return
        try:
            event_payload = {"event": "ops.dashboard.updated", **payload.to_dict()}
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                loop.create_task(
                    self._event_bus.publish(event_payload, event_type="ops.dashboard.updated")
                )
            else:
                asyncio.run(
                    self._event_bus.publish(event_payload, event_type="ops.dashboard.updated")
                )
        except Exception:
            return


__all__ = ["OpsHealthDashboardService", "OpsHealthDashboard"]
