"""Shadow CLI helpers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.interfaces.shadow.slack_bridge import ShadowChannelConfig, ShadowPayload, SlackShadowBridge
from src.interfaces.gui.shadow_api import ShadowGuiApi
from src.shadow.session import ShadowSessionOrchestrator
from src.shadow.store import ShadowStateStore

DEFAULT_CHANNELS_PATH = Path("config/shadow/channels.yaml")
DEFAULT_EVENT_LOG = Path("logs/events/shadow_session.jsonl")

__all__ = ["shadow_replay", "shadow_serve", "shadow_status", "shadow_test"]


def shadow_test(
    *,
    channel: str,
    ticket_path: Path,
    channels_path: Path = DEFAULT_CHANNELS_PATH,
    feature_flags: Path = Path("config/feature_flags.yaml"),
    message_log: Path = Path("logs/shadow/slack_messages.jsonl"),
) -> Mapping[str, Any]:
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    channel_config = _load_channel(channel, channels_path)
    payload = ShadowPayload(
        event_type="ticket.proposed",
        ticket_id=str(ticket.get("ticket_id") or ticket.get("id") or "unknown"),
        title=str(ticket.get("title") or "Shadow Ticket"),
        body_md=json.dumps(ticket, ensure_ascii=False, indent=2),
        badges=["shadow"],
        risk_state=ticket.get("risk_state"),
        board_mode=ticket.get("board_mode"),
        health_state=ticket.get("health_state"),
        consent_reference_id=ticket.get("consent_reference_id"),
        runbook_link=channel_config.runbook_ref,
        actions=[],
    )
    bridge = SlackShadowBridge(
        feature_flags_path=feature_flags,
        message_log=message_log,
    )
    result = bridge.publish(payload, channel_config=channel_config)
    return {"status": result.get("status"), "message_ts": result.get("message_ts")}


def shadow_replay(
    *,
    since_hours: int,
    event_log: Path = DEFAULT_EVENT_LOG,
    replay_log: Path = Path("logs/events/shadow_replay.jsonl"),
    store_path: Path = Path("data/shadow_state.db"),
) -> Mapping[str, Any]:
    store = ShadowStateStore(db_path=store_path)
    count = 0
    if event_log.exists():
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        for line in event_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = record.get("ts")
            try:
                ts_val = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except Exception:
                continue
            if ts_val < cutoff:
                continue
            payload = record.get("payload")
            if isinstance(payload, dict):
                orchestrator = ShadowSessionOrchestrator(
                    event_bus=None,  # type: ignore[arg-type]
                    store=store,
                    event_log=replay_log,
                )
                orchestrator.process_event(record.get("event_type", "unknown"), payload)
                count += 1
    return {"status": "ok", "replayed": count}


def shadow_status(*, store_path: Path = Path("data/shadow_state.db")) -> Mapping[str, Any]:
    store = ShadowStateStore(db_path=store_path)
    return {
        "status": "ok",
        "tickets": [ticket.to_dict() for ticket in store.list_tickets()],
        "alerts": [alert.to_dict() for alert in store.list_alerts()],
        "acks": [ack.to_dict() for ack in store.list_acks()],
    }


def shadow_serve(
    *,
    host: str = "127.0.0.1",
    port: int = 7777,
    token: str | None = None,
    token_path: Path = Path("config/shadow/tokens.yaml"),
    store_path: Path = Path("data/shadow_state.db"),
    event_log: Path = DEFAULT_EVENT_LOG,
    dry_run: bool = False,
) -> Mapping[str, Any]:
    store = ShadowStateStore(db_path=store_path)
    api = ShadowGuiApi(store=store, token_path=token_path, event_log=event_log)
    status = api.status()
    status.update({"host": host, "port": port})
    if dry_run:
        return {"status": "ok", "mode": "dry-run", **status}
    if token:
        status["token_hint"] = token[:4] + "..." if len(token) > 4 else token
    return {"status": "stub", "mode": "not_started", **status}


def _load_channel(channel: str, path: Path) -> ShadowChannelConfig:
    if not path.exists():
        return ShadowChannelConfig(channel_id=channel, runbook_ref="RUN-SHADOW-01")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    channels = payload.get("channels") if isinstance(payload, dict) else {}
    entry = channels.get(channel) if isinstance(channels, dict) else None
    if not isinstance(entry, dict):
        return ShadowChannelConfig(channel_id=channel, runbook_ref="RUN-SHADOW-01")
    return ShadowChannelConfig(
        channel_id=str(entry.get("channel_id") or channel),
        threading_mode=str(entry.get("threading_mode") or "ticket"),
        allow_ack=bool(entry.get("allow_ack", True)),
        runbook_ref=entry.get("runbook_ref") or "RUN-SHADOW-01",
        severity_filter=entry.get("severity_filter"),
    )
