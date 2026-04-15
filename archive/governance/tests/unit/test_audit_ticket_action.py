from pathlib import Path

from src.audit.trace import log_ticket_action


def test_log_ticket_action_includes_auto_execute(tmp_path: Path) -> None:
    out = tmp_path / "ticket_action.jsonl"
    delta = {
        "before": {"qty": 1},
        "after": {"qty": 1},
        "diff": {},
        "decision": "approve",
        "document_hash": "sha256:" + "0" * 64,
        "consent_version": "v1",
        "expires_at": None,
        "ack_user": None,
        "ack_evidence": None,
    }
    record = log_ticket_action(
        ticket_id="T1",
        action="approve",
        actor="tester",
        board_mode="normal",
        kill_switch_state="none",
        spread_status="normal",
        profit_readiness_status="ok",
        reduce_only=False,
        risk_disclosure_state="ok",
        auto_execute=True,
        spread_state={"EURUSD": {"state": "normal"}},
        health_state="ok",
        cfg_hash="sha256:" + "1" * 64,
        data_hash="sha256:" + "2" * 64,
        latency_data_status="ok",
        slippage_data_status="ok",
        delta=delta,
        notes="example",
        path=out,
    )
    assert record["auto_execute"] is True
    payload = out.read_text(encoding="utf-8")
    assert '"auto_execute": true' in payload
