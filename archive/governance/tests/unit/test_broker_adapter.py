from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from src.brokers.adapter import BrokerAccessDenied, BrokerOrderRejected, BrokerOrderRequest
from src.brokers.sandbox import SandboxAdapter
from src.compliance.risk_disclosure import RiskDisclosureState
from src.compliance.risk_disclosure_enforcer import RiskDisclosureEnforcer
from src.security.access import AccessGovernanceService


def _write_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _build_access_service(tmp_path: Path) -> AccessGovernanceService:
    now = datetime.now(timezone.utc)
    principal_path = tmp_path / "principals.jsonl"
    device_path = tmp_path / "devices.jsonl"
    review_path = tmp_path / "reviews.jsonl"
    risk_state_path = tmp_path / "risk_disclosure_state.json"

    state = RiskDisclosureState(
        status="accepted",
        version="v1",
        consent_reference_id="consent-1",
        accepted_at=now,
        expires_at=now + timedelta(days=30),
        device_fingerprint="fp-001",
    )
    risk_state_path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _write_jsonl(
        principal_path,
        {
            "principal_id": "principal-1",
            "type": "user",
            "display_name": "Trader One",
            "roles": ["trader"],
            "status": "active",
            "mfa_enrolled": True,
        },
    )
    _write_jsonl(
        device_path,
        {
            "device_id": "device-1",
            "principal_id": "principal-1",
            "platform": "macos",
            "fingerprint": "fp-001",
            "registered_at": now.isoformat(),
            "last_seen_at": now.isoformat(),
            "risk_consent_version": "v1",
            "filevault_enabled": True,
            "keychain_integrity": True,
            "security_scan": {"last_scan_at": now.isoformat(), "status": "ok"},
        },
    )

    risk_enforcer = RiskDisclosureEnforcer(
        state_path=risk_state_path,
        metrics_path=tmp_path / "risk_metrics.jsonl",
        audit_path=tmp_path / "risk_audit.jsonl",
        validation_playbook_path=tmp_path / "risk_playbook.yaml",
    )
    return AccessGovernanceService(
        principal_registry_path=principal_path,
        device_registry_path=device_path,
        review_registry_path=review_path,
        audit_log_path=tmp_path / "access_audit.jsonl",
        metrics_path=tmp_path / "access_metrics.jsonl",
        validation_playbook_path=tmp_path / "access_playbook.yaml",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
        risk_enforcer=risk_enforcer,
    )


def test_sandbox_order_accepts_when_access_allowed(tmp_path: Path) -> None:
    access_service = _build_access_service(tmp_path)
    audit_path = tmp_path / "broker_audit.jsonl"
    metrics_path = tmp_path / "broker_metrics.jsonl"
    adapter = SandboxAdapter(
        access_service=access_service,
        audit_log_path=audit_path,
        metrics_path=metrics_path,
        kill_switch_path=tmp_path / "kill_switch.json",
    )

    order = adapter.place_order(
        BrokerOrderRequest(
            ticket_id="ticket-1",
            symbol="EURUSD",
            side="buy",
            quantity=0.1,
            price=1.2345,
        ),
        principal_id="principal-1",
        device_id="device-1",
    )

    assert order.status == "acknowledged"
    assert order.ticket_id == "ticket-1"
    assert order.adapter == "sandbox"
    assert audit_path.exists()
    assert metrics_path.exists()


def test_sandbox_order_rejects_when_access_denied(tmp_path: Path) -> None:
    access_service = AccessGovernanceService(
        principal_registry_path=tmp_path / "missing_principals.jsonl",
        device_registry_path=tmp_path / "missing_devices.jsonl",
        review_registry_path=tmp_path / "missing_reviews.jsonl",
        audit_log_path=tmp_path / "access_audit.jsonl",
        metrics_path=tmp_path / "access_metrics.jsonl",
        validation_playbook_path=tmp_path / "access_playbook.yaml",
        ops_worklog_path=tmp_path / "ops_worklog.jsonl",
    )
    adapter = SandboxAdapter(
        access_service=access_service,
        audit_log_path=tmp_path / "broker_audit.jsonl",
        metrics_path=tmp_path / "broker_metrics.jsonl",
        kill_switch_path=tmp_path / "kill_switch.json",
    )

    with pytest.raises(BrokerAccessDenied):
        adapter.place_order(
            BrokerOrderRequest(
                ticket_id="ticket-2",
                symbol="USDJPY",
                side="sell",
                quantity=0.2,
            ),
            principal_id="missing-principal",
            device_id="device-2",
        )


def test_sandbox_order_rejects_on_kill_switch(tmp_path: Path) -> None:
    access_service = _build_access_service(tmp_path)
    kill_switch_path = tmp_path / "kill_switch.json"
    kill_switch_path.write_text(
        json.dumps({"state": "stop"}, ensure_ascii=False), encoding="utf-8"
    )
    adapter = SandboxAdapter(
        access_service=access_service,
        audit_log_path=tmp_path / "broker_audit.jsonl",
        metrics_path=tmp_path / "broker_metrics.jsonl",
        kill_switch_path=kill_switch_path,
    )

    with pytest.raises(BrokerOrderRejected):
        adapter.place_order(
            BrokerOrderRequest(
                ticket_id="ticket-3",
                symbol="GBPUSD",
                side="buy",
                quantity=0.3,
            ),
            principal_id="principal-1",
            device_id="device-1",
        )
