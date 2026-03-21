"""Shadow GUI API helpers for ticket/alert snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from src.brokers.fill_shadow import FillShadowStore
from src.interfaces.gui.allocation_surface import summarize_allocation_surface
from src.interfaces.gui.candidate_surface import summarize_candidate_surface
from src.interfaces.gui.shadow_baseline import (
    build_shadow_baseline_summary,
    write_shadow_baseline_report,
)
from src.interfaces.gui.shadow_daily_review import (
    build_daily_shadow_review_summary,
    write_daily_shadow_review_report,
)
from src.interfaces.gui.shadow_daily_ops import (
    build_daily_shadow_ops_summary,
    write_daily_shadow_ops_report,
)
from src.interfaces.gui.shadow_feedback_validation_surface import (
    summarize_shadow_feedback_validation_result,
)
from src.interfaces.gui.shadow_feedback_rollout_history import (
    load_shadow_feedback_rollout_history,
)
from src.interfaces.gui.shadow_next_stage_surface import (
    DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER,
    summarize_shadow_next_stage_execution,
)
from src.interfaces.gui.shadow_discrepancy_ledger import (
    DEFAULT_DISCREPANCY_LEDGER_PATH,
    build_shadow_baseline_readiness_summary,
    build_shadow_discrepancy_summary,
    load_shadow_discrepancy_ledger,
)
from src.portfolio.shadow_stage_gate import build_shadow_stage_gate_summary
from src.portfolio.shadow_soak import build_shadow_soak_summary
from src.shadow.store import ShadowStateStore

DEFAULT_TOKEN_PATH = Path("config/shadow/tokens.yaml")
DEFAULT_EVENT_LOG = Path("logs/events/shadow_session.jsonl")
DEFAULT_SIGNAL_LOG = Path("logs/events/signal.generated.jsonl")
DEFAULT_METRICS_PATH = Path("metrics/shadow_gui.jsonl")
DEFAULT_AUDIT_LOG = Path("logs/audit/shadow_gui.jsonl")
DEFAULT_REPORT_DIR = Path("reports/analysis/shadow")
DEFAULT_DAILY_SHADOW_HISTORY = Path("reports/analysis/shadow/daily_shadow_review_history.jsonl")
DEFAULT_DAILY_SHADOW_DISCREPANCY_LEDGER = DEFAULT_DISCREPANCY_LEDGER_PATH
DEFAULT_DAILY_SHADOW_NOTIFICATION_LOG = Path("logs/ops/shadow_daily_notifications.jsonl")
DEFAULT_SHADOW_FEEDBACK_ROLLOUT_HISTORY = Path("reports/analysis/shadow/shadow_feedback_rollout_history.jsonl")
DEFAULT_BROKER_SHADOW_EVENT_LOG = Path("logs/broker/shadow_events.jsonl")
DEFAULT_BROKER_SHADOW_SESSION_LOG = Path("logs/broker/shadow_sessions.jsonl")


class ShadowAuthError(Exception):
    """Raised when Shadow GUI token authentication fails."""


@dataclass(slots=True)
class ShadowGuiApi:
    store: ShadowStateStore
    token_path: Path = DEFAULT_TOKEN_PATH
    event_log: Path = DEFAULT_EVENT_LOG
    signal_log: Path = DEFAULT_SIGNAL_LOG
    metrics_path: Path = DEFAULT_METRICS_PATH
    audit_log: Path = DEFAULT_AUDIT_LOG
    report_dir: Path = DEFAULT_REPORT_DIR
    daily_shadow_history_path: Path = DEFAULT_DAILY_SHADOW_HISTORY
    daily_shadow_discrepancy_ledger_path: Path = DEFAULT_DAILY_SHADOW_DISCREPANCY_LEDGER
    daily_shadow_notification_log: Path = DEFAULT_DAILY_SHADOW_NOTIFICATION_LOG
    shadow_feedback_rollout_history_path: Path = DEFAULT_SHADOW_FEEDBACK_ROLLOUT_HISTORY
    broker_shadow_event_log: Path = DEFAULT_BROKER_SHADOW_EVENT_LOG
    broker_shadow_session_log: Path = DEFAULT_BROKER_SHADOW_SESSION_LOG
    shadow_next_stage_execution_ledger_path: Path = DEFAULT_SHADOW_NEXT_STAGE_EXECUTION_LEDGER

    def list_tickets(
        self,
        *,
        token: str | None = None,
        mode: str | None = None,
        since: datetime | None = None,
    ) -> dict[str, object]:
        self._require_token(token)
        tickets = []
        for ticket in self.store.list_tickets():
            updated_at = _parse_ts(ticket.updated_at)
            if since and updated_at and updated_at < since:
                continue
            payload = ticket.payload
            if mode and str(payload.get("mode") or payload.get("profile") or "") != mode:
                continue
            tickets.append(_format_ticket(ticket.ticket_id, ticket.status, payload, ticket.updated_at))
        return {
            "schema_version": "shadow.ticket.v1",
            "generated_at": _utcnow_iso(),
            "tickets": tickets,
        }

    def list_alerts(
        self,
        *,
        token: str | None = None,
        severity: str | None = None,
    ) -> dict[str, object]:
        self._require_token(token)
        alerts = []
        for alert in self.store.list_alerts():
            payload = alert.payload
            alert_severity = payload.get("severity") or payload.get("level")
            if severity and str(alert_severity) != severity:
                continue
            alerts.append(
                {
                    "alert_id": alert.alert_id,
                    "event_type": alert.event_type,
                    "payload": payload,
                    "created_at": alert.created_at,
                }
            )
        return {
            "schema_version": "shadow.alert.v1",
            "generated_at": _utcnow_iso(),
            "alerts": alerts,
        }

    def record_ack(
        self,
        *,
        reference_id: str,
        actor: str | None = None,
        note: str | None = None,
        token: str | None = None,
    ) -> dict[str, object]:
        self._require_token(token)
        ack_id = _shadow_ack_id(reference_id)
        recorded_at = _utcnow_iso()
        self.store.record_ack(ack_id, source="gui", reference_id=reference_id, actor=actor)
        self._append_audit(
            {
                "event": "shadow.gui.ack_received",
                "ts": recorded_at,
                "ack_id": ack_id,
                "reference_id": reference_id,
                "actor": actor,
                "note": note,
            }
        )
        self._append_metrics({"ts": recorded_at, "event": "shadow.gui.ack_received"})
        return {
            "schema_version": "shadow.ack.v1",
            "ack_id": ack_id,
            "reference_id": reference_id,
            "status": "accepted",
            "recorded_at": recorded_at,
        }

    def stream_events(
        self,
        *,
        token: str | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, object]]:
        self._require_token(token)
        events: list[dict[str, object]] = []
        if not self.event_log.exists():
            return events
        for line in self.event_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_ts(record.get("ts"))
            if since and ts and ts < since:
                continue
            if "event_type" in record:
                events.append(record)
        return events

    def record_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        token: str | None = None,
    ) -> dict[str, object]:
        self._require_token(token)
        recorded_at = _utcnow_iso()
        record = {
            "event_type": event_type,
            "payload": payload,
            "ts": recorded_at,
        }
        self.event_log.parent.mkdir(parents=True, exist_ok=True)
        with self.event_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
        self._append_metrics({"ts": recorded_at, "event": event_type})
        return {
            "status": "ok",
            "event_type": event_type,
            "recorded_at": recorded_at,
        }

    def status(self, *, stage_gate_summary: dict[str, Any] | None = None) -> dict[str, object]:
        tokens = _load_tokens(self.token_path)
        allocation_summary = _summarize_allocation_decisions(self.signal_log, limit=200)
        candidate_snapshot = summarize_candidate_surface(self.signal_log, limit=200)
        shadow_next_stage_execution_state = summarize_shadow_next_stage_execution(
            self.shadow_next_stage_execution_ledger_path
        )
        daily_shadow_review_summary = build_daily_shadow_review_summary(
            allocation_summary=allocation_summary,
            candidate_snapshot=candidate_snapshot,
            fill_store=self._fill_shadow_store(),
            broker_shadow_event_log=self.broker_shadow_event_log,
            shadow_next_stage_execution_state=shadow_next_stage_execution_state,
            history_path=self.daily_shadow_history_path,
            discrepancy_ledger_path=self.daily_shadow_discrepancy_ledger_path,
            stage_gate_summary=stage_gate_summary,
        )
        discrepancy_ledger = load_shadow_discrepancy_ledger(self.daily_shadow_discrepancy_ledger_path)
        shadow_discrepancy_summary = build_shadow_discrepancy_summary(
            daily_shadow_review_summary,
            discrepancy_ledger,
        )
        shadow_readiness_summary = build_shadow_baseline_readiness_summary(
            daily_shadow_review_summary,
            shadow_discrepancy_summary,
        )
        daily_shadow_review_summary["discrepancy_summary"] = shadow_discrepancy_summary
        daily_shadow_review_summary["shadow_readiness_summary"] = shadow_readiness_summary
        daily_shadow_review_summary["stage_gate_summary"] = build_shadow_stage_gate_summary(
            daily_shadow_review_summary
        )
        daily_shadow_review_summary["soak_summary"] = build_shadow_soak_summary(
            daily_shadow_review_summary
        )
        daily_shadow_ops_summary = build_daily_shadow_ops_summary(
            daily_shadow_review_summary,
            focused_validation_output_dir=self.report_dir / "feedback_validation",
            rollout_history_path=self.shadow_feedback_rollout_history_path,
        )
        shadow_feedback_validation_result = (
            dict(daily_shadow_ops_summary.get("shadow_feedback_validation_result") or {})
            if isinstance(daily_shadow_ops_summary.get("shadow_feedback_validation_result"), Mapping)
            else summarize_shadow_feedback_validation_result(
                output_dir=self.report_dir / "feedback_validation"
            )
        )
        shadow_feedback_rollout_alignment = (
            dict(daily_shadow_ops_summary.get("shadow_feedback_rollout_alignment") or {})
            if isinstance(daily_shadow_ops_summary.get("shadow_feedback_rollout_alignment"), Mapping)
            else {}
        )
        return {
            "status": "ok",
            "token_count": len(tokens),
            "event_log": str(self.event_log),
            "signal_log": str(self.signal_log),
            "allocation_summary": allocation_summary,
            "candidate_snapshot": candidate_snapshot,
            "shadow_baseline_summary": build_shadow_baseline_summary(
                allocation_summary=allocation_summary,
                candidate_snapshot=candidate_snapshot,
            ),
            "stage_gate_summary": daily_shadow_review_summary.get("stage_gate_summary"),
            "daily_shadow_review_summary": daily_shadow_review_summary,
            "shadow_discrepancy_summary": shadow_discrepancy_summary,
            "shadow_readiness_summary": shadow_readiness_summary,
            "shadow_stage_gate_summary": daily_shadow_review_summary.get("stage_gate_summary") or {},
            "shadow_soak_summary": daily_shadow_review_summary.get("soak_summary") or {},
            "shadow_next_stage_execution_template": daily_shadow_review_summary.get("next_stage_execution_template") or {},
            "shadow_next_stage_execution_state": shadow_next_stage_execution_state,
            "shadow_feedback_summary": daily_shadow_review_summary.get("shadow_feedback_summary") or {},
            "shadow_feedback_override_packet": daily_shadow_ops_summary.get("shadow_feedback_override_packet") or {},
            "shadow_feedback_validation_result": shadow_feedback_validation_result,
            "shadow_feedback_rollout_alignment": shadow_feedback_rollout_alignment,
            "shadow_feedback_rollout_history": load_shadow_feedback_rollout_history(
                self.shadow_feedback_rollout_history_path
            ),
            "daily_shadow_ops_summary": daily_shadow_ops_summary,
            "schema_path": "docs/schema/shadow_gui.yaml",
        }

    def allocation_summary(
        self,
        *,
        token: str | None = None,
        limit: int = 200,
    ) -> dict[str, object]:
        self._require_token(token)
        return _summarize_allocation_decisions(self.signal_log, limit=limit)

    def shadow_baseline_report(
        self,
        *,
        token: str | None = None,
    ) -> dict[str, object]:
        self._require_token(token)
        allocation_summary = _summarize_allocation_decisions(self.signal_log, limit=200)
        candidate_snapshot = summarize_candidate_surface(self.signal_log, limit=200)
        return write_shadow_baseline_report(
            allocation_summary=allocation_summary,
            candidate_snapshot=candidate_snapshot,
            output_dir=self.report_dir,
        )

    def daily_shadow_review_report(
        self,
        *,
        token: str | None = None,
        stage_gate_summary: dict[str, Any] | None = None,
        window_hours: int = 24,
    ) -> dict[str, object]:
        self._require_token(token)
        allocation_summary = _summarize_allocation_decisions(self.signal_log, limit=200)
        candidate_snapshot = summarize_candidate_surface(self.signal_log, limit=200)
        shadow_next_stage_execution_state = summarize_shadow_next_stage_execution(
            self.shadow_next_stage_execution_ledger_path
        )
        return write_daily_shadow_review_report(
            allocation_summary=allocation_summary,
            candidate_snapshot=candidate_snapshot,
            fill_store=self._fill_shadow_store(),
            broker_shadow_event_log=self.broker_shadow_event_log,
            shadow_next_stage_execution_state=shadow_next_stage_execution_state,
            history_path=self.daily_shadow_history_path,
            discrepancy_ledger_path=self.daily_shadow_discrepancy_ledger_path,
            stage_gate_summary=stage_gate_summary,
            output_dir=self.report_dir,
            window_hours=window_hours,
        )

    def daily_shadow_ops_report(
        self,
        *,
        token: str | None = None,
        stage_gate_summary: dict[str, Any] | None = None,
        window_hours: int = 24,
    ) -> dict[str, object]:
        self._require_token(token)
        allocation_summary = _summarize_allocation_decisions(self.signal_log, limit=200)
        candidate_snapshot = summarize_candidate_surface(self.signal_log, limit=200)
        shadow_next_stage_execution_state = summarize_shadow_next_stage_execution(
            self.shadow_next_stage_execution_ledger_path
        )
        review_summary = build_daily_shadow_review_summary(
            allocation_summary=allocation_summary,
            candidate_snapshot=candidate_snapshot,
            fill_store=self._fill_shadow_store(),
            broker_shadow_event_log=self.broker_shadow_event_log,
            shadow_next_stage_execution_state=shadow_next_stage_execution_state,
            history_path=self.daily_shadow_history_path,
            discrepancy_ledger_path=self.daily_shadow_discrepancy_ledger_path,
            stage_gate_summary=stage_gate_summary,
            window_hours=window_hours,
        )
        return write_daily_shadow_ops_report(
            summary=review_summary,
            output_dir=self.report_dir,
            notification_log=self.daily_shadow_notification_log,
            rollout_history_path=self.shadow_feedback_rollout_history_path,
        )

    def _require_token(self, token: str | None) -> None:
        tokens = _load_tokens(self.token_path)
        if not tokens:
            return
        if token is None or token not in tokens:
            raise ShadowAuthError("invalid shadow token")

    def _append_metrics(self, payload: dict[str, object]) -> None:
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self.metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _append_audit(self, payload: dict[str, object]) -> None:
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _fill_shadow_store(self) -> FillShadowStore:
        return FillShadowStore(
            event_log_path=self.broker_shadow_event_log,
            session_log_path=self.broker_shadow_session_log,
        )


def _load_tokens(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    tokens = payload.get("tokens") if isinstance(payload, dict) else None
    if not isinstance(tokens, list):
        return set()
    values: set[str] = set()
    for entry in tokens:
        if isinstance(entry, str):
            values.add(entry)
        elif isinstance(entry, dict):
            token = entry.get("token") or entry.get("value")
            if token:
                values.add(str(token))
    return values


def _format_ticket(ticket_id: str, status: str, payload: dict[str, Any], updated_at: str) -> dict[str, Any]:
    return {
        "ticket_id": ticket_id,
        "symbol": payload.get("symbol") or "UNKNOWN",
        "side": payload.get("side") or payload.get("direction") or "buy",
        "score": payload.get("score") or 0,
        "issued_at": payload.get("issued_at") or payload.get("timestamp") or updated_at,
        "ttl_sec": payload.get("ttl_sec") or 0,
        "status": payload.get("status") or status,
        "board_mode": payload.get("board_mode") or "normal",
        "kill_switch_state": payload.get("kill_switch_state") or "running",
        "ack_state": payload.get("ack_state") or "pending",
        "ack_required": bool(payload.get("ack_required", False)),
    }


def _parse_ts(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _shadow_ack_id(reference_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"shadow_ack_{reference_id}_{stamp}"


def _summarize_allocation_decisions(path: Path, *, limit: int) -> dict[str, object]:
    if not path.exists():
        return {
            "status": "ok",
            "count": 0,
            "summary": {"accept": 0, "reject": 0, "defer": 0, "resize": 0, "replace": 0},
            "recent": [],
            "portfolio_surface": {
                "active_slots": {"count": 0, "slots": []},
                "portfolio_group_occupancy": [],
                "exposure_bucket_occupancy": [],
            },
        }

    payload = summarize_allocation_surface(path, limit=limit)
    decisions = payload.get("decisions")
    recent = decisions[-5:] if isinstance(decisions, list) else []
    return {
        "status": payload.get("status", "ok"),
        "count": payload.get("count", 0),
        "summary": payload.get("summary", {}),
        "reason_summary": payload.get("reason_summary", []),
        "conflict_summary": payload.get("conflict_summary", []),
        "winner_conflict_summary": payload.get("winner_conflict_summary", []),
        "winner_bias_summary": payload.get("winner_bias_summary", []),
        "winner_review_summary": payload.get("winner_review_summary", []),
        "recent": recent,
        "portfolio_surface": payload.get("portfolio_surface", {}),
    }


__all__ = ["ShadowAuthError", "ShadowGuiApi"]
