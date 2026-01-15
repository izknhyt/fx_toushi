from __future__ import annotations

import json
from pathlib import Path

from src.compliance.risk_disclosure_enforcer import RiskDisclosureEnforcer


def test_risk_disclosure_enforcer_prompt(tmp_path: Path) -> None:
    state_path = tmp_path / "risk_disclosure_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "risk_disclosure_state.v2",
                "status": "expired",
                "version": "v1",
                "consent_reference_id": "consent-1",
                "device_fingerprint": "fp-1",
            }
        ),
        encoding="utf-8",
    )
    enforcer = RiskDisclosureEnforcer(
        state_path=state_path,
        metrics_path=tmp_path / "metrics" / "risk_consent.jsonl",
        audit_path=tmp_path / "logs" / "audit" / "risk_consent.jsonl",
        validation_playbook_path=tmp_path / "docs" / "validation_playbook" / "AC44_risk_consent.yaml",
    )
    decision = enforcer.enforce(action="kill_switch", device_fingerprint="fp-1")
    assert decision.decision == "prompt"
    assert decision.required_steps == ["re-ack"]


def test_risk_disclosure_enforcer_device_mismatch(tmp_path: Path) -> None:
    state_path = tmp_path / "risk_disclosure_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "risk_disclosure_state.v2",
                "status": "accepted",
                "version": "v1",
                "device_fingerprint": "fp-1",
            }
        ),
        encoding="utf-8",
    )
    enforcer = RiskDisclosureEnforcer(
        state_path=state_path,
        metrics_path=tmp_path / "metrics" / "risk_consent.jsonl",
        audit_path=tmp_path / "logs" / "audit" / "risk_consent.jsonl",
        validation_playbook_path=tmp_path / "docs" / "validation_playbook" / "AC44_risk_consent.yaml",
    )
    decision = enforcer.enforce(action="approve", device_fingerprint="fp-2")
    assert decision.decision == "deny"
