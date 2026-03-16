"""Shadow GUI API helpers for ticket/alert snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from src.shadow.store import ShadowStateStore

DEFAULT_TOKEN_PATH = Path("config/shadow/tokens.yaml")
DEFAULT_EVENT_LOG = Path("logs/events/shadow_session.jsonl")
DEFAULT_SIGNAL_LOG = Path("logs/events/signal.generated.jsonl")
DEFAULT_METRICS_PATH = Path("metrics/shadow_gui.jsonl")
DEFAULT_AUDIT_LOG = Path("logs/audit/shadow_gui.jsonl")


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

    def status(self) -> dict[str, object]:
        tokens = _load_tokens(self.token_path)
        return {
            "status": "ok",
            "token_count": len(tokens),
            "event_log": str(self.event_log),
            "signal_log": str(self.signal_log),
            "allocation_summary": _summarize_allocation_decisions(self.signal_log, limit=200),
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
    summary = {"accept": 0, "reject": 0, "defer": 0, "resize": 0, "replace": 0}
    if not path.exists():
        return {"status": "ok", "count": 0, "summary": summary, "recent": []}

    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-max(1, limit) :]:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") not in {"signal.generated", "portfolio.admission"}:
            continue
        if not payload.get("allocation_decision"):
            continue
        status = str(payload.get("status") or "").strip().lower()
        if status not in summary:
            continue
        summary[status] += 1
        decision = payload.get("allocation_decision")
        reason_code = None
        if isinstance(decision, dict):
            reason_code = decision.get("reason_code")
        records.append(
            {
                "ts": payload.get("ts"),
                "strategy_id": payload.get("strategy_id"),
                "symbol": payload.get("symbol"),
                "status": status,
                "reason_code": reason_code,
            }
        )
    records.sort(key=lambda item: str(item.get("ts") or ""))
    return {"status": "ok", "count": len(records), "summary": summary, "recent": records[-5:]}


__all__ = ["ShadowAuthError", "ShadowGuiApi"]
