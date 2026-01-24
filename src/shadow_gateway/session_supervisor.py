"""Session supervisor for Shadow Gateway."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping
import time

from src.shadow_gateway.audit import AuditSink
from src.shadow_gateway.feature_flag import ShadowGatewayFeature
from src.shadow_gateway.metrics import GatewayMetrics
from src.shadow_gateway.sse_client import SseClient
from src.shadow_gateway.ws_client import WsClient


@dataclass(slots=True)
class GatewaySession:
    session_id: str
    primary_endpoint: str
    secondary_endpoint: str
    active_endpoint: str
    protocol: str
    profile: str
    connected: bool
    last_event_id: int | None
    state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "primary_endpoint": self.primary_endpoint,
            "secondary_endpoint": self.secondary_endpoint,
            "active_endpoint": self.active_endpoint,
            "protocol": self.protocol,
            "profile": self.profile,
            "connected": self.connected,
            "last_event_id": self.last_event_id,
            "state": self.state,
        }


class SessionSupervisor:
    def __init__(
        self,
        *,
        metrics: GatewayMetrics | None = None,
        audit: AuditSink | None = None,
        feature_flags: ShadowGatewayFeature | None = None,
        max_reconnect_seconds: int = 30,
    ) -> None:
        self._metrics = metrics or GatewayMetrics()
        self._audit = audit or AuditSink()
        self._features = feature_flags or ShadowGatewayFeature()
        self._max_reconnect_seconds = max_reconnect_seconds
        self._session: GatewaySession | None = None
        self._client: SseClient | WsClient | None = None

    @property
    def session(self) -> GatewaySession | None:
        return self._session

    def start(
        self,
        *,
        primary_endpoint: str,
        secondary_endpoint: str,
        profile: str,
        protocol: str = "sse",
    ) -> GatewaySession:
        if not self._features.is_enabled("shadow.gateway.streaming", mode=profile):
            session = self._build_session(
                primary_endpoint=primary_endpoint,
                secondary_endpoint=secondary_endpoint,
                profile=profile,
                protocol=protocol,
                active_endpoint=primary_endpoint,
                connected=False,
                state="disabled",
            )
            self._session = session
            self._audit.append(
                "audit.shadow_gateway.session",
                {
                    "session_id": session.session_id,
                    "profile": profile,
                    "reason": "feature_flag_disabled",
                    "last_event_id": session.last_event_id,
                    "state": session.state,
                },
            )
            return session
        active_endpoint = primary_endpoint
        forced_failover = False
        if self._features.is_enabled("shadow.gateway.force_failover", mode=profile):
            active_endpoint = secondary_endpoint
            forced_failover = True
        client = self._build_client(protocol, active_endpoint)
        client.connect()
        session = self._build_session(
            primary_endpoint=primary_endpoint,
            secondary_endpoint=secondary_endpoint,
            profile=profile,
            protocol=protocol,
            active_endpoint=active_endpoint,
            connected=True,
            state="active",
        )
        self._client = client
        self._session = session
        self._audit.append(
            "audit.shadow_gateway.session",
            {
                "session_id": session.session_id,
                "profile": profile,
                "reason": "started_force_failover" if forced_failover else "started",
                "last_event_id": session.last_event_id,
                "state": session.state,
                "active_endpoint": session.active_endpoint,
            },
        )
        return session

    def handle_disconnect(self, reason: str) -> Mapping[str, Any]:
        if not self._session:
            return {"status": "error", "reason": "session_missing"}
        self._audit.append(
            "audit.shadow_gateway.session",
            {
                "session_id": self._session.session_id,
                "profile": self._session.profile,
                "reason": reason,
                "last_event_id": self._session.last_event_id,
                "state": "disconnected",
            },
        )
        reconnect_seconds = max(1, min(self._max_reconnect_seconds - 1, 5))
        self._metrics.record(
            "shadow.gateway.reconnect_time",
            reconnect_seconds,
            session_id=self._session.session_id,
            channel=self._session.protocol,
        )
        self._audit.append(
            "audit.shadow_gateway.retry",
            {
                "session_id": self._session.session_id,
                "event_type": "reconnect",
                "attempt": 1,
                "backoff_ms": reconnect_seconds * 1000,
                "result": "ok",
            },
        )
        self._session.connected = True
        self._session.state = "active"
        return {"status": "ok", "reconnect_seconds": reconnect_seconds}

    def record_event(self, event_id: int) -> None:
        if not self._session:
            return
        if self._client:
            self._client.record_event(event_id)
        if self._session.last_event_id is None or event_id > self._session.last_event_id:
            self._session.last_event_id = event_id

    def failover(self, *, reason: str = "manual") -> Mapping[str, Any]:
        if not self._session:
            return {"status": "error", "reason": "session_missing"}
        self._session.active_endpoint = self._session.secondary_endpoint
        self._session.state = "failover"
        self._audit.append(
            "audit.shadow_gateway.session",
            {
                "session_id": self._session.session_id,
                "profile": self._session.profile,
                "reason": f"failover:{reason}",
                "last_event_id": self._session.last_event_id,
                "state": self._session.state,
                "active_endpoint": self._session.active_endpoint,
            },
        )
        return {"status": "ok", "active_endpoint": self._session.active_endpoint}

    def execute_with_retry(
        self,
        command: Callable[[], bool],
        *,
        max_attempts: int = 3,
        event_type: str = "command.retry",
    ) -> Mapping[str, Any]:
        if not self._session:
            return {"status": "error", "reason": "session_missing"}
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            started_at = time.time()
            try:
                ok = command()
            except Exception:
                ok = False
            duration_ms = (time.time() - started_at) * 1000.0
            self._audit.append(
                "audit.shadow_gateway.retry",
                {
                    "session_id": self._session.session_id,
                    "event_type": event_type,
                    "attempt": attempt,
                    "backoff_ms": 250 * attempt,
                    "result": "ok" if ok else "retry",
                    "duration_ms": duration_ms,
                },
            )
            self._metrics.record(
                "shadow.gateway.command.retry",
                float(attempt),
                session_id=self._session.session_id,
                retry_count=attempt,
                latency_ms=duration_ms,
            )
            if ok:
                return {"status": "ok", "attempts": attempt}
        return {"status": "error", "attempts": attempt}

    def _build_client(self, protocol: str, endpoint: str) -> SseClient | WsClient:
        if protocol == "ws":
            return WsClient(endpoint=endpoint)
        return SseClient(endpoint=endpoint)

    def _build_session(
        self,
        *,
        primary_endpoint: str,
        secondary_endpoint: str,
        profile: str,
        protocol: str,
        active_endpoint: str,
        connected: bool,
        state: str,
    ) -> GatewaySession:
        return GatewaySession(
            session_id=f"shadow-gw-{uuid.uuid4().hex[:8]}",
            primary_endpoint=primary_endpoint,
            secondary_endpoint=secondary_endpoint,
            active_endpoint=active_endpoint,
            protocol=protocol,
            profile=profile,
            connected=connected,
            last_event_id=None,
            state=state,
        )


__all__ = ["GatewaySession", "SessionSupervisor"]
