"""SSE client stub for Shadow Gateway."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SseClient:
    endpoint: str
    connected: bool = False
    last_event_id: int | None = None

    def connect(self) -> dict[str, object]:
        self.connected = True
        return {"status": "connected", "endpoint": self.endpoint}

    def disconnect(self, *, reason: str | None = None) -> dict[str, object]:
        self.connected = False
        return {"status": "disconnected", "endpoint": self.endpoint, "reason": reason}

    def record_event(self, event_id: int) -> None:
        if self.last_event_id is None or event_id > self.last_event_id:
            self.last_event_id = event_id


__all__ = ["SseClient"]
