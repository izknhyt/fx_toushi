from __future__ import annotations

import json
from pathlib import Path
from pytest import MonkeyPatch

from src.interfaces.gui.tauri_app.serializer import board_get_snapshot, TicketPayloadSerializer


def test_board_snapshot_includes_ticket_payload_version(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
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
    ticket = {
        "ticket_id": "T1",
        "symbol": "USDJPY",
        "timeframe": "H1",
        "strategy_id": "s1",
        "action": "buy",
        "quantity": 1.0,
        "gate_context": {"spread": {"state": "watch"}},
    }
    snapshot = board_get_snapshot(tickets=[ticket], manifest_path=manifest)
    assert snapshot["ticket_payload_version"] == TicketPayloadSerializer.version
    assert snapshot["tickets"][0]["ticket_payload_version"] == TicketPayloadSerializer.version
    assert snapshot["board"]["guardrails"]["spread_status"] == "normal"
