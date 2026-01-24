from __future__ import annotations

from src.interfaces.gui.tauri_app.viewmodel import build_viewmodel


def test_build_viewmodel_maps_ticket_cards() -> None:
    snapshot = {
        "tickets": [
            {"ticket_id": "t1", "symbol": "USDJPY", "side": "buy", "status": "pending"},
            {"ticket_id": "t2", "pair": "EURUSD", "direction": "sell", "state": "approved"},
        ]
    }
    viewmodel = build_viewmodel(snapshot)
    assert viewmodel["cards"][0]["ticket_id"] == "t1"
    assert viewmodel["cards"][1]["symbol"] == "EURUSD"
