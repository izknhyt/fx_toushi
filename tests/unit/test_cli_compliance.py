"""Tests for compliance CLI helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.interfaces.cli.compliance import DEFAULT_RISK_STATE, ack, refresh, status


def test_compliance_status_defaults_to_pending(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    payload = status()

    assert payload["risk_disclosure"] == "pending"
    assert payload["required_action"] == "ack"
    assert payload["path"] == str(DEFAULT_RISK_STATE)


def test_compliance_ack_updates_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    ack_state = ack(note="accept terms", user="tester", force=False)

    assert ack_state["status"] == "accepted"
    saved = Path("risk_state.json").read_text(encoding="utf-8")
    assert "accepted" in saved


def test_compliance_refresh_marks_expired(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    expired_state = {
        "schema_version": "risk_disclosure_state.v2",
        "status": "accepted",
        "version": "v1",
        "consent_reference_id": "consent-test",
        "accepted_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "document_hash": None,
    }
    Path("risk_state.json").write_text(
        __import__("json").dumps(expired_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    refreshed = refresh()

    assert refreshed["status"] in {"expired", "pending"}
