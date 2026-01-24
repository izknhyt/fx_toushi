from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from src.brokers.adapter import BrokerAdapterRegistry
from src.compliance.risk_disclosure import RiskDisclosureState
from src.compliance.risk_disclosure_enforcer import RiskDisclosureEnforcer
from src.execution.order_router import OrderDispatchRejected, OrderRouter
from src.infra.broker_rules import load_broker_rules
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


def _write_feature_flags(path: Path) -> None:
    payload = {
        "schema_version": "feature_flags.v1",
        "defaults": {
            "paper": {"brokers.api_enabled": False, "brokers.api_sandbox_only": True},
            "backtest": {"brokers.api_enabled": False, "brokers.api_sandbox_only": True},
            "live": {"brokers.api_enabled": False, "brokers.api_sandbox_only": True},
        },
        "definitions": {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_order_router_applies_marketable_limit(tmp_path: Path) -> None:
    access_service = _build_access_service(tmp_path)
    feature_flags = tmp_path / "feature_flags.json"
    _write_feature_flags(feature_flags)
    registry = BrokerAdapterRegistry(
        feature_flags_path=feature_flags,
        audit_log_path=tmp_path / "broker_audit.jsonl",
        metrics_path=tmp_path / "broker_metrics.jsonl",
        kill_switch_path=tmp_path / "kill_switch.json",
        access_service=access_service,
    )
    router = OrderRouter(
        adapter_registry=registry,
        broker_rules=load_broker_rules(),
        audit_log_path=tmp_path / "router_audit.jsonl",
        metrics_path=tmp_path / "router_metrics.jsonl",
        kill_switch_path=tmp_path / "kill_switch.json",
    )

    order = router.submit(
        {
            "ticket_id": "ticket-1",
            "symbol": "EURUSD",
            "side": "buy",
            "quantity": 0.1,
            "entry_type": "marketable_limit",
            "entry_price": 1.1000,
            "principal_id": "principal-1",
            "device_id": "device-1",
            "adapter": "sandbox",
            "profile": "paper",
        }
    )

    assert order.status == "acknowledged"
    assert order.payload["price"] == pytest.approx(1.10012, rel=1e-6)


def test_order_router_rejects_on_kill_switch(tmp_path: Path) -> None:
    access_service = _build_access_service(tmp_path)
    feature_flags = tmp_path / "feature_flags.json"
    _write_feature_flags(feature_flags)
    kill_switch_path = tmp_path / "kill_switch.json"
    kill_switch_path.write_text(json.dumps({"state": "stop"}), encoding="utf-8")
    registry = BrokerAdapterRegistry(
        feature_flags_path=feature_flags,
        audit_log_path=tmp_path / "broker_audit.jsonl",
        metrics_path=tmp_path / "broker_metrics.jsonl",
        kill_switch_path=kill_switch_path,
        access_service=access_service,
    )
    router = OrderRouter(
        adapter_registry=registry,
        broker_rules=load_broker_rules(),
        audit_log_path=tmp_path / "router_audit.jsonl",
        metrics_path=tmp_path / "router_metrics.jsonl",
        kill_switch_path=kill_switch_path,
    )

    with pytest.raises(OrderDispatchRejected):
        router.submit(
            {
                "ticket_id": "ticket-2",
                "symbol": "EURUSD",
                "side": "buy",
                "quantity": 0.1,
                "entry_type": "marketable_limit",
                "entry_price": 1.1000,
                "principal_id": "principal-1",
                "device_id": "device-1",
                "adapter": "sandbox",
                "profile": "paper",
            }
        )


def test_order_router_requires_principal(tmp_path: Path) -> None:
    feature_flags = tmp_path / "feature_flags.json"
    _write_feature_flags(feature_flags)
    registry = BrokerAdapterRegistry(feature_flags_path=feature_flags)
    router = OrderRouter(
        adapter_registry=registry,
        broker_rules=load_broker_rules(),
        audit_log_path=tmp_path / "router_audit.jsonl",
        metrics_path=tmp_path / "router_metrics.jsonl",
        kill_switch_path=tmp_path / "kill_switch.json",
    )

    with pytest.raises(OrderDispatchRejected):
        router.submit(
            {
                "ticket_id": "ticket-3",
                "symbol": "EURUSD",
                "side": "buy",
                "quantity": 0.1,
                "entry_type": "marketable_limit",
                "entry_price": 1.1000,
            }
        )
