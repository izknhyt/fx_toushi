from __future__ import annotations

import json
from pathlib import Path

from src.interfaces.gui.shadow_api import ShadowAuthError, ShadowGuiApi
from src.shadow.store import ShadowStateStore


def _write_tokens(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(
        [
            "schema_version: shadow_tokens.v1",
            "tokens:",
            f"  - token: {token}",
        ]
    )
    path.write_text(payload + "\n", encoding="utf-8")


def test_shadow_gui_requires_token(tmp_path: Path) -> None:
    token_path = tmp_path / "tokens.yaml"
    _write_tokens(token_path, "secret")
    store = ShadowStateStore(db_path=tmp_path / "shadow.db")
    api = ShadowGuiApi(store=store, token_path=token_path)

    try:
        api.list_tickets(token="bad")
    except ShadowAuthError:
        pass
    else:
        raise AssertionError("Expected ShadowAuthError")


def test_shadow_gui_lists_and_acks(tmp_path: Path) -> None:
    token_path = tmp_path / "tokens.yaml"
    _write_tokens(token_path, "secret")
    store = ShadowStateStore(db_path=tmp_path / "shadow.db")
    store.upsert_ticket("T-1", status="proposed", payload={"symbol": "EURUSD"})
    store.add_alert("A-1", event_type="health.degraded", payload={"severity": "warn"})

    metrics_path = tmp_path / "metrics" / "shadow_gui.jsonl"
    audit_log = tmp_path / "logs" / "audit" / "shadow_gui.jsonl"
    api = ShadowGuiApi(
        store=store,
        token_path=token_path,
        metrics_path=metrics_path,
        audit_log=audit_log,
    )

    tickets = api.list_tickets(token="secret")
    assert tickets["schema_version"] == "shadow.ticket.v1"
    assert tickets["tickets"][0]["ticket_id"] == "T-1"

    alerts = api.list_alerts(token="secret")
    assert alerts["alerts"][0]["alert_id"] == "A-1"

    ack = api.record_ack(reference_id="T-1", actor="ops", token="secret")
    assert ack["status"] == "accepted"
    assert metrics_path.exists()
    assert audit_log.exists()
    last_metric = json.loads(metrics_path.read_text(encoding="utf-8").splitlines()[-1])
    assert last_metric["event"] == "shadow.gui.ack_received"


def test_shadow_gui_status_and_allocation_summary_include_admission_counts(tmp_path: Path) -> None:
    token_path = tmp_path / "tokens.yaml"
    _write_tokens(token_path, "secret")
    store = ShadowStateStore(db_path=tmp_path / "shadow.db")
    signal_log = tmp_path / "logs" / "events" / "signal.generated.jsonl"
    signal_log.parent.mkdir(parents=True, exist_ok=True)
    signal_log.write_text(
        "\n".join(
            [
                    json.dumps(
                        {
                            "event": "portfolio.admission",
                            "ts": "2026-03-16T13:00:00Z",
                            "strategy_id": "alpha",
                            "symbol": "USDJPY",
                            "status": "accept",
                        "allocation_decision": {"reason_code": "selected"},
                    }
                ),
                    json.dumps(
                        {
                            "event": "portfolio.admission",
                            "ts": "2026-03-16T13:01:00Z",
                            "strategy_id": "beta",
                            "symbol": "USDJPY",
                            "status": "reject",
                        "allocation_decision": {"reason_code": "tie_break_lost"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    api = ShadowGuiApi(store=store, token_path=token_path, signal_log=signal_log)

    summary = api.allocation_summary(token="secret")
    assert summary["count"] == 2
    assert summary["summary"]["accept"] == 1
    assert summary["summary"]["reject"] == 1

    status = api.status()
    assert status["signal_log"] == str(signal_log)
    assert status["allocation_summary"]["summary"]["accept"] == 1
