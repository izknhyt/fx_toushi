"""Slack shadow bridge for posting shadow events."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(slots=True)
class ShadowChannelConfig:
    channel_id: str
    threading_mode: str = "ticket"
    allow_ack: bool = True
    runbook_ref: str | None = None
    severity_filter: str | None = None


@dataclass(slots=True)
class SlackAction:
    action_id: str
    label: str
    style: str = "secondary"
    callback: str = "ack_only"
    requires_note: bool = False


@dataclass(slots=True)
class ShadowPayload:
    event_type: str
    ticket_id: str | None
    title: str
    body_md: str
    badges: list[str]
    risk_state: str | None
    board_mode: str | None
    health_state: str | None
    consent_reference_id: str | None
    runbook_link: str | None
    actions: list[SlackAction]

    def to_dict(self) -> dict[str, object]:
        return {
            "event_type": self.event_type,
            "ticket_id": self.ticket_id,
            "title": self.title,
            "body_md": self.body_md,
            "badges": list(self.badges),
            "risk_state": self.risk_state,
            "board_mode": self.board_mode,
            "health_state": self.health_state,
            "consent_reference_id": self.consent_reference_id,
            "runbook_link": self.runbook_link,
            "actions": [action.__dict__ for action in self.actions],
        }


@dataclass(slots=True)
class AckReceipt:
    ack_id: str
    ticket_id: str
    status: str
    recorded_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "ack_id": self.ack_id,
            "ticket_id": self.ticket_id,
            "status": self.status,
            "recorded_at": self.recorded_at,
        }


class SlackShadowBridge:
    """Publish shadow payloads to Slack (logged locally in this implementation)."""

    def __init__(
        self,
        *,
        feature_flags_path: Path = Path("config/feature_flags.yaml"),
        message_log: Path = Path("logs/shadow/slack_messages.jsonl"),
        audit_log: Path = Path("logs/audit/shadow_interactions.jsonl"),
        metrics_path: Path = Path("metrics/shadow_bridge.jsonl"),
        ops_worklog_path: Path = Path("ops_worklog.jsonl"),
    ) -> None:
        self._feature_flags_path = feature_flags_path
        self._message_log = message_log
        self._audit_log = audit_log
        self._metrics_path = metrics_path
        self._ops_worklog_path = ops_worklog_path
        self._message_log.parent.mkdir(parents=True, exist_ok=True)
        self._audit_log.parent.mkdir(parents=True, exist_ok=True)
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)

    def publish(self, payload: ShadowPayload, *, channel_config: ShadowChannelConfig) -> dict[str, object]:
        if not _shadow_enabled(self._feature_flags_path, profile=_resolve_profile()):
            return {"status": "skipped", "reason": "feature_disabled"}
        if not _passes_severity_filter(payload, channel_config):
            return {"status": "skipped", "reason": "severity_filtered"}
        message_id = _slack_ts()
        record = {
            "ts": _utcnow_iso(),
            "message_ts": message_id,
            "channel_id": channel_config.channel_id,
            "payload": payload.to_dict(),
            "runbook_ref": channel_config.runbook_ref,
        }
        _append_jsonl(self._message_log, record)
        self._append_metrics("shadow.message.posted", channel_id=channel_config.channel_id)
        return {"status": "ok", "message_ts": message_id}

    def handle_interaction(self, payload: Mapping[str, Any]) -> dict[str, object]:
        if not _shadow_enabled(self._feature_flags_path, profile=_resolve_profile()):
            return {"status": "skipped", "reason": "feature_disabled"}
        ticket_id = str(payload.get("ticket_id") or payload.get("reference_id") or "unknown")
        actor = payload.get("actor")
        note = payload.get("note")
        action_id = payload.get("action_id") or payload.get("action")
        ack_id = str(payload.get("ack_id") or _shadow_ack_id(ticket_id))
        record = {
            "event": "audit.shadow_interaction",
            "ts": _utcnow_iso(),
            "ack_id": ack_id,
            "ticket_id": ticket_id,
            "actor": actor,
            "note": note,
            "action_id": action_id,
            "source": payload.get("source") or "slack",
        }
        _append_jsonl(self._audit_log, record)
        _append_jsonl(
            Path(self._ops_worklog_path),
            {
                "ts": record["ts"],
                "task": "shadow_ack",
                "actor": actor,
                "ticket_id": ticket_id,
                "note": note,
                "action_id": action_id,
            },
        )
        self._append_metrics("shadow.interaction.recorded", channel_id=payload.get("channel_id"))
        receipt = AckReceipt(
            ack_id=ack_id,
            ticket_id=ticket_id,
            status="recorded",
            recorded_at=record["ts"],
        )
        return {"status": "ok", "receipt": receipt.to_dict()}

    def sync_threads(self, *, ticket_id: str, channel_id: str | None = None) -> dict[str, object]:
        if not _shadow_enabled(self._feature_flags_path, profile=_resolve_profile()):
            return {"status": "skipped", "reason": "feature_disabled"}
        message_id = _slack_ts()
        record = {
            "ts": _utcnow_iso(),
            "message_ts": message_id,
            "ticket_id": ticket_id,
            "channel_id": channel_id,
            "event": "shadow.thread.sync",
        }
        _append_jsonl(self._message_log, record)
        self._append_metrics("shadow.thread.synced", channel_id=channel_id)
        return {"status": "ok", "message_ts": message_id, "ticket_id": ticket_id}

    def _append_metrics(self, event: str, *, channel_id: str | None = None) -> None:
        _append_jsonl(
            self._metrics_path,
            {"ts": _utcnow_iso(), "event": event, "channel_id": channel_id},
        )


def _append_jsonl(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _shadow_enabled(path: Path, *, profile: str) -> bool:
    if not path.exists():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    defaults = payload.get("defaults") if isinstance(payload, Mapping) else None
    if not isinstance(defaults, Mapping):
        return False
    profile_defaults = defaults.get(profile)
    if not isinstance(profile_defaults, Mapping):
        return False
    return bool(profile_defaults.get("shadow.slack_enabled", False))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slack_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")


def _passes_severity_filter(payload: ShadowPayload, channel_config: ShadowChannelConfig) -> bool:
    if not channel_config.severity_filter:
        return True
    filter_token = channel_config.severity_filter
    return filter_token in payload.event_type or filter_token in payload.badges


def _resolve_profile() -> str:
    return os.getenv("TRADECTL_PROFILE", "live")


def _shadow_ack_id(ticket_id: str) -> str:
    return f"ack_{ticket_id}_{_slack_ts()}"


__all__ = [
    "AckReceipt",
    "ShadowChannelConfig",
    "SlackAction",
    "ShadowPayload",
    "SlackShadowBridge",
]
