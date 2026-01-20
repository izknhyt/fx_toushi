from pathlib import Path

from src.shadow.session import ShadowSessionOrchestrator
from src.shadow.store import ShadowStateStore


class _DummyEventBus:
    async def subscribe(self, event_type: str):  # pragma: no cover - not used in unit test
        return iter([])


def test_orchestrator_process_event(tmp_path: Path) -> None:
    store = ShadowStateStore(db_path=tmp_path / "shadow.db", ttl_hours=1)
    orchestrator = ShadowSessionOrchestrator(
        event_bus=_DummyEventBus(), store=store, event_log=tmp_path / "events.log"
    )

    orchestrator.process_event(
        "ticket.proposed", {"ticket_id": "t-1", "status": "pending", "title": "test"}
    )
    orchestrator.process_event("health.changed", {"alert_id": "a-1", "status": "warn"})
    orchestrator.process_event(
        "shadow.ack", {"ack_id": "ack-1", "source": "slack", "ticket_id": "t-1"}
    )

    assert store.list_tickets()[0].ticket_id == "t-1"
    assert store.list_alerts()[0].alert_id == "a-1"
    assert store.list_acks()[0].reference_id == "t-1"
