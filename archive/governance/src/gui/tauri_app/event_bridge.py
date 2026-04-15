"""Event bridge for GUI state updates and command responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4


@dataclass(slots=True)
class GuiEvent:
    event_id: str
    event_type: str
    payload: dict[str, Any]
    ts: str

    @staticmethod
    def create(event_type: str, payload: dict[str, Any]) -> "GuiEvent":
        return GuiEvent(
            event_id=f"gui-{uuid4().hex}",
            event_type=event_type,
            payload=payload,
            ts=_utcnow_iso(),
        )


Subscriber = Callable[[GuiEvent], None]


@dataclass(slots=True)
class Subscription:
    token: str
    topic: str
    handler: Subscriber


class GuiEventBridge:
    """Simple in-memory Pub/Sub for GUI events."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, Subscription] = {}
        self._history: list[GuiEvent] = []

    def subscribe(self, topic: str, handler: Subscriber) -> str:
        token = uuid4().hex
        self._subscriptions[token] = Subscription(token=token, topic=topic, handler=handler)
        return token

    def unsubscribe(self, token: str) -> None:
        self._subscriptions.pop(token, None)

    def publish(self, event_type: str, payload: dict[str, Any]) -> GuiEvent:
        event = GuiEvent.create(event_type, payload)
        self._history.append(event)
        for subscription in list(self._subscriptions.values()):
            if _matches_topic(subscription.topic, event.event_type):
                subscription.handler(event)
        return event

    def history(self) -> list[GuiEvent]:
        return list(self._history)


def _matches_topic(topic: str, event_type: str) -> bool:
    if topic.endswith("*"):
        prefix = topic[:-1]
        if event_type.startswith(prefix):
            return True
        if prefix.endswith(":"):
            return event_type.startswith(prefix.replace(":", "."))
        return False
    return topic == event_type


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["GuiEvent", "GuiEventBridge"]
