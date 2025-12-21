from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.ticket.builder import DefaultTicketBuilder, GateState, TicketDraft


def _make_draft(metadata: dict[str, object] | None = None) -> TicketDraft:
    meta = {"ticket_id": "T-1", "determinism_hash": "sha256:fixture"}
    if metadata:
        meta.update(metadata)
    return TicketDraft(symbol="USDJPY", action="buy", qty=1.0, metadata=meta)


def test_hands_off_sizing_uses_fallback_bridge_metrics(tmp_path: Path, monkeypatch) -> None:
    bridge_dir = tmp_path / "scoreboard" / "bridge"
    bridge_dir.mkdir(parents=True)
    sample_bridge = {
        "week": "2025-W01",
        "strategies": [
            {
                "id": "m1_baseline_ma_rsi",
                "pf_all": 1.3,
                "sharpe": 1.1,
                "maxdd": 7.0,
                "watchlist_reasons": [],
            }
        ],
    }
    (bridge_dir / "2025-W01.json").write_text(json.dumps(sample_bridge), encoding="utf-8")
    monkeypatch.setenv("TRADECTL_BRIDGE_DIR", str(bridge_dir))

    gate_state = GateState()
    gate_state.auto_execute = True
    builder = DefaultTicketBuilder()
    # inject a minimal lot ladder rule
    builder._lot_ladder = [builder._lot_ladder[0]] if builder._lot_ladder else []  # type: ignore[attr-defined]
    if not builder._lot_ladder:
        from src.execution.alpha_overlay import LotLadderRule

        builder._lot_ladder = [LotLadderRule(pf_min=1.2, sharpe_min=1.0, maxdd_max=8.0, watchlist_max=0, size_factor=1.1)]  # type: ignore[attr-defined]

    artifact = builder.build(_make_draft(), gate_state)
    meta = artifact.payload["metadata"]
    assert meta["auto_execute_factor"] >= 1.0


def test_hands_off_sizing_skips_when_auto_execute_off() -> None:
    gate_state = GateState()
    gate_state.auto_execute = False
    builder = DefaultTicketBuilder()
    artifact = builder.build(_make_draft(), gate_state)
    meta = artifact.payload["metadata"]
    assert meta.get("auto_execute_factor", 1.0) == 1.0
