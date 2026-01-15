from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.compliance.device_binding import DeviceBindingService
from src.interfaces.cli import create_cli_app


def test_risk_consent_enforce_and_device_cli(tmp_path: Path, monkeypatch) -> None:
    state_path = tmp_path / "risk_disclosure_state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "risk_disclosure_state.v2",
                "status": "expired",
                "version": "v1",
                "device_fingerprint": "fp-1",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RISK_DISCLOSURE_STATE_PATH", str(state_path))

    device_service = DeviceBindingService(
        registry_path=tmp_path / "device_bindings.json",
        audit_path=tmp_path / "device_bindings_audit.jsonl",
        allow_plaintext=True,
    )
    monkeypatch.setattr(
        "src.interfaces.cli.compliance_risk.DeviceBindingService",
        lambda: device_service,
    )
    from src.compliance.risk_disclosure_enforcer import RiskDisclosureEnforcer

    def _enforcer_factory():
        return RiskDisclosureEnforcer(
            state_path=state_path,
            metrics_path=tmp_path / "metrics" / "risk_consent.jsonl",
            audit_path=tmp_path / "logs" / "audit" / "risk_consent.jsonl",
            validation_playbook_path=tmp_path / "docs" / "validation_playbook" / "AC44_risk_consent.yaml",
        )

    monkeypatch.setattr("src.interfaces.cli.compliance_risk.RiskDisclosureEnforcer", _enforcer_factory)

    app = create_cli_app()
    runner = CliRunner()

    enforce = runner.invoke(
        app,
        [
            "compliance",
            "risk-disclosure",
            "enforce",
            "--action",
            "approve",
            "--device",
            "fp-1",
            "--json",
        ],
    )
    assert enforce.exit_code == 0, enforce.stdout
    payload = json.loads(enforce.stdout)
    assert payload["decision"] == "prompt"

    register = runner.invoke(
        app,
        [
            "compliance",
            "device",
            "register",
            "--user",
            "ops",
            "--fingerprint",
            "fp-1",
            "--json",
        ],
    )
    assert register.exit_code == 0, register.stdout

    listed = runner.invoke(
        app,
        ["compliance", "device", "list", "--json"],
    )
    assert listed.exit_code == 0, listed.stdout
    devices_payload = json.loads(listed.stdout)
    assert devices_payload["devices"]
