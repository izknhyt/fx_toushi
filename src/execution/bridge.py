"""Execution Bridge logging helpers for StageGuard exercises."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_METRICS_PATH = Path("metrics/execution_bridge.jsonl")
DEFAULT_REPORT_DIR = Path("reports/execution")


class ExecutionBridgeLogError(RuntimeError):
    """Raised when execution bridge data cannot be persisted."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ExecutionBridgeRecord:
    timestamp: str
    mode: str
    broker: str
    stage: str
    session_id: str
    latency_ms: float
    error_rate: float
    stage_guard_decision: str
    notes: str | None
    metrics_path: str
    report_path: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "mode": self.mode,
            "broker": self.broker,
            "stage": self.stage,
            "session_id": self.session_id,
            "latency_ms": self.latency_ms,
            "error_rate": self.error_rate,
            "stage_guard_decision": self.stage_guard_decision,
            "notes": self.notes,
            "metrics_path": self.metrics_path,
            "report_path": self.report_path,
        }


def log_execution_bridge(
    *,
    mode: str,
    broker: str,
    stage: str,
    session_id: str,
    latency_ms: float,
    error_rate: float,
    decision: str,
    notes: str | None = None,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    report_dir: Path = DEFAULT_REPORT_DIR,
    report_date: date | None = None,
) -> ExecutionBridgeRecord:
    """Append execution bridge metrics and render a Markdown report."""

    timestamp = _utcnow()
    metrics_entry = {
        "timestamp": timestamp,
        "mode": mode,
        "broker": broker,
        "stage": stage,
        "session_id": session_id,
        "latency_ms": latency_ms,
        "error_rate": error_rate,
        "decision": decision,
        "notes": notes,
    }
    try:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metrics_entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise ExecutionBridgeLogError(f"Unable to append metrics to {metrics_path}") from exc

    try:
        report_path = _render_report(
            metrics=metrics_entry,
            report_dir=report_dir,
            report_date=report_date or datetime.now(timezone.utc).date(),
        )
    except OSError as exc:
        raise ExecutionBridgeLogError(f"Unable to write report into {report_dir}") from exc

    return ExecutionBridgeRecord(
        timestamp=timestamp,
        mode=mode,
        broker=broker,
        stage=stage,
        session_id=session_id,
        latency_ms=latency_ms,
        error_rate=error_rate,
        stage_guard_decision=decision,
        notes=notes,
        metrics_path=str(metrics_path),
        report_path=str(report_path),
    )


def _render_report(
    *,
    metrics: dict[str, Any],
    report_dir: Path,
    report_date: date,
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"live_bridge_{report_date:%Y%m%d}.md"
    content = "\n".join(
        [
            f"# Execution Bridge Evidence — {report_date:%Y-%m-%d}",
            "",
            f"- Generated At: {metrics['timestamp']}",
            f"- Mode: {metrics['mode']}",
            f"- Broker: {metrics['broker']}",
            f"- StageGuard Stage: {metrics['stage']}",
            f"- Session ID: {metrics['session_id']}",
            "",
            "## Metrics",
            "",
            f"- Latency p95 (ms): {metrics['latency_ms']}",
            f"- Error Rate: {metrics['error_rate']:.2%}",
            "",
            "## StageGuard Exercise",
            "",
            f"- Decision: {metrics['decision']}",
            f"- Notes: {metrics.get('notes') or 'n/a'}",
            "",
            "## Actions",
            "",
            "- Capture CLI logs and attach to RUN-BROKER-01 evidence bundle.",
            "- Update ops_worklog task `profit_readiness` if latency > 350ms or error_rate > 1%.",
            "",
        ]
    )
    report_path.write_text(content, encoding="utf-8")
    return report_path
