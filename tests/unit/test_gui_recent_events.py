from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from pytest import MonkeyPatch

from src.interfaces.gui.tauri_app.serializer import board_get_snapshot, collect_recent_events


def test_board_snapshot_includes_ticket_action_fields(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    manifest = tmp_path / "data_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "strategies": {
                    "m1_baseline_ma_rsi": {
                        "dataset_path": "data/mock.parquet",
                        "dataset_sha256": "deadbeef",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RISK_DISCLOSURE_STATE_PATH", str(tmp_path / "risk_state.json"))

    ticket_action_log = tmp_path / "logs" / "audit" / "ticket_action.jsonl"
    ticket_action_log.parent.mkdir(parents=True, exist_ok=True)
    ticket_action_log.write_text(
        json.dumps(
            {
                "ts": datetime.utcnow().isoformat(),
                "record_type": "ticket.action",
                "ticket_id": "T-1",
                "action": "approve",
                "actor": "alice",
                "board_mode": "normal",
                "kill_switch_state": "none",
                "spread_status": "normal",
                "profit_readiness_status": "ok",
                "reduce_only": False,
                "risk_disclosure_state": "pending",
                "cfg_hash": "sha256:cfg",
                "data_hash": "sha256:data",
                "consent_reference_id": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = board_get_snapshot(
        tickets=[],
        manifest_path=manifest,
        ticket_action_log=ticket_action_log,
        events_lookback=timedelta(days=1),
    )
    ticket_events = snapshot["recent_events"]["ticket"]
    assert ticket_events
    record = ticket_events[-1]
    assert record["ticket_id"] == "T-1"
    assert record["kill_switch_state"] == "none"
    assert record["spread_status"] == "normal"
    assert record["profit_readiness_status"] == "ok"
    assert record["reduce_only"] is False
    assert record["risk_disclosure_state"] == "pending"
    assert record["cfg_hash"].startswith("sha256:")
    assert record["data_hash"].startswith("sha256:")


def test_collect_recent_events_merges_bus_and_audit(tmp_path: Path) -> None:
    class FakeBus:
        def __init__(self, records: list[dict[str, object]]) -> None:
            self._records = records

        def replay(
            self,
            from_ts: datetime,
            *,
            to_ts: datetime | None = None,
            event_types: list[str] | None = None,
            batch_size: int = 256,
        ):
            _ = (from_ts, to_ts, event_types, batch_size)
            return iter(self._records)

    ticket_action_log = tmp_path / "logs" / "audit" / "ticket_action.jsonl"
    ticket_action_log.parent.mkdir(parents=True, exist_ok=True)
    ticket_action_log.write_text(
        json.dumps(
            {
                "ts": datetime.utcnow().isoformat(),
                "record_type": "ticket.action",
                "ticket_id": "T-2",
                "action": "reject",
                "actor": "bob",
                "board_mode": "guarded",
                "kill_switch_state": "soft_stop",
                "spread_status": "cooldown",
                "profit_readiness_status": "guarded",
                "reduce_only": True,
                "risk_disclosure_state": "pending",
                "cfg_hash": "sha256:cfg2",
                "data_hash": "sha256:data2",
                "consent_reference_id": "00000000-0000-0000-0000-000000000000",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    bus_records = [
        {"ts": "2025-12-07T00:00:00Z", "event_type": "health.changed", "event": {"status": "degraded"}},
        {"ts": "2025-12-07T00:00:01Z", "event_type": "execution.fill", "event": {"id": "fill-1"}},
    ]
    events = collect_recent_events(
        FakeBus(bus_records),
        from_ts=datetime.utcnow() - timedelta(days=1),
        per_channel_limit=2,
        ticket_action_log=ticket_action_log,
    )

    assert events["health"][0]["event_type"] == "health.changed"
    assert events["execution"][0]["event_type"] == "execution.fill"
    ticket_events = events["ticket"]
    assert ticket_events[-1]["ticket_id"] == "T-2"
    assert ticket_events[-1]["reduce_only"] is True
    assert ticket_events[-1]["consent_reference_id"] == "00000000-0000-0000-0000-000000000000"


def test_collect_recent_events_fills_placeholders(tmp_path: Path) -> None:
    class EmptyBus:
        def replay(self, from_ts, *, to_ts=None, event_types=None, batch_size: int = 256):
            return iter([])

    events = collect_recent_events(
        EmptyBus(),
        from_ts=datetime.utcnow() - timedelta(days=1),
        per_channel_limit=2,
        ticket_action_log=None,
    )
    assert all(events[channel] for channel in ["ticket", "gate", "health", "execution"])
    assert events["ticket"][0]["source"] == "placeholder"
