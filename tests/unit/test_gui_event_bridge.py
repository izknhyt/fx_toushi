from __future__ import annotations

from src.interfaces.gui.tauri_app.event_bridge import GuiEventBridge


def test_event_bridge_publish_subscribe() -> None:
    bridge = GuiEventBridge()
    seen: list[str] = []

    def _handler(event) -> None:
        seen.append(event.event_type)

    token = bridge.subscribe("state:*", _handler)
    bridge.publish("state.ready", {"ok": True})
    bridge.publish("ticket.update", {"id": "t1"})
    bridge.unsubscribe(token)

    assert seen == ["state.ready"]
