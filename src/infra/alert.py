"""Alert dispatcher with file + SMTP fallback."""

from __future__ import annotations

import json
import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

DEFAULT_ALERT_LOG = Path("logs/events/alerts.jsonl")


class AlertSendError(RuntimeError):
    """Raised when alert delivery fails."""


class AlertChannelConfigError(RuntimeError):
    """Raised when alert channel config is missing."""


class AlertTemplateError(RuntimeError):
    """Raised when alert payload cannot be rendered."""


@dataclass(slots=True)
class AlertEvent:
    severity: str
    message: str
    reason: str | None = None
    runbook_ref: str | None = None
    metadata: Mapping[str, Any] | None = None
    ts: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts or _utcnow_iso(),
            "severity": self.severity,
            "message": self.message,
            "reason": self.reason,
            "runbook_ref": self.runbook_ref,
            "metadata": dict(self.metadata or {}),
        }


class AlertDispatcher:
    def __init__(self, *, log_path: Path = DEFAULT_ALERT_LOG) -> None:
        self._log_path = log_path

    def dispatch(
        self,
        *,
        level: str | None = None,
        message: str | None = None,
        event: AlertEvent | None = None,
        raise_on_error: bool = False,
    ) -> None:
        if event is None:
            if level is None or message is None:
                raise AlertTemplateError("level and message are required")
            event = AlertEvent(severity=level, message=message)
        payload = event.to_dict()
        self._append_log(payload)
        logger.log(
            getattr(logging, payload["severity"].upper(), logging.INFO),
            payload["message"],
        )
        if _smtp_configured():
            try:
                self._send_email(payload)
            except (AlertChannelConfigError, AlertSendError) as exc:
                logger.warning("alert.dispatch.failed", extra={"error": str(exc)})
                if raise_on_error:
                    raise

    def test_channel(self, *, channel: str, to_address: str) -> dict[str, object]:
        if channel != "smtp":
            raise AlertChannelConfigError(f"unsupported channel: {channel}")
        if not _smtp_configured():
            raise AlertChannelConfigError("SMTP configuration is missing")
        payload = AlertEvent(
            severity="info",
            message="Alert channel test",
            reason="channel_test",
            metadata={"channel": channel},
        ).to_dict()
        self._send_email(payload, override_to=to_address)
        return {"status": "ok", "channel": channel, "to": to_address}

    def _append_log(self, payload: Mapping[str, Any]) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _send_email(self, payload: Mapping[str, Any], *, override_to: str | None = None) -> None:
        host = os.getenv("ALERT_SMTP_HOST")
        port = int(os.getenv("ALERT_SMTP_PORT", "587"))
        user = os.getenv("ALERT_SMTP_USER")
        password = os.getenv("ALERT_SMTP_PASS")
        sender = os.getenv("ALERT_SMTP_FROM", user or "")
        recipients = override_to or os.getenv("ALERT_SMTP_TO", "")
        if not host or not sender or not recipients:
            raise AlertChannelConfigError("SMTP configuration is missing")
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = recipients
        msg["Subject"] = _subject(payload)
        msg.set_content(_render_body(payload))
        try:
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                smtp.starttls()
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
        except OSError as exc:
            raise AlertSendError(str(exc)) from exc


def _smtp_configured() -> bool:
    return bool(
        os.getenv("ALERT_SMTP_HOST")
        and os.getenv("ALERT_SMTP_TO")
        and (os.getenv("ALERT_SMTP_FROM") or os.getenv("ALERT_SMTP_USER"))
    )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _subject(payload: Mapping[str, Any]) -> str:
    severity = str(payload.get("severity", "info")).upper()
    reason = payload.get("reason") or "alert"
    return f"[tradectl][{severity}] {reason}"


def _render_body(payload: Mapping[str, Any]) -> str:
    lines = [
        f"Severity: {payload.get('severity')}",
        f"Message: {payload.get('message')}",
        f"Reason: {payload.get('reason')}",
        f"Runbook: {payload.get('runbook_ref')}",
    ]
    meta = payload.get("metadata") or {}
    if meta:
        lines.append(f"Metadata: {json.dumps(meta, ensure_ascii=False)}")
    return "\n".join(lines)

__all__ = [
    "AlertDispatcher",
    "AlertEvent",
    "AlertSendError",
    "AlertChannelConfigError",
    "AlertTemplateError",
]
