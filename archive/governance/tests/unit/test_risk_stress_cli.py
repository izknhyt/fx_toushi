import json
import yaml

import pytest

from src.interfaces.cli import risk_stress
from src.risk.stress_lab import MarginStressLab


def _dump_yaml(payload):
    return "# JSON\n" + json.dumps(payload)


def test_stress_run_dry_run_uses_temp_paths(tmp_path, monkeypatch):
    policy_path = tmp_path / "risk_policy.yaml"
    policy_path.write_text(
        _dump_yaml(
            {
                "profiles": {
                    "paper": {
                        "risk_limits": {"margin_warn": 0.4, "margin_throttle": 0.6},
                        "kill_switch": {"drawdown_threshold_pct": {"daily": 2.5, "weekly": 5.0}},
                    }
                }
            },
        ),
        encoding="utf-8",
    )
    presets_path = tmp_path / "presets.yaml"
    presets_path.write_text(
        _dump_yaml(
            {
                "presets": [
                    {
                        "id": "covid",
                        "kind": "historical",
                        "shock_profile": {
                            "drawdown_pct": 10,
                            "weekly_drawdown_pct": 15,
                            "loss_streak": 4,
                            "margin_peak": 0.7,
                            "r_eff_peak": 1.2,
                            "corr_hotness": 0.9,
                        },
                    }
                ]
            },
        ),
        encoding="utf-8",
    )

    def _factory():
        return MarginStressLab(
            policy_path=policy_path,
            presets_path=presets_path,
            metrics_path=tmp_path / "metrics.jsonl",
            audit_log=tmp_path / "audit.jsonl",
            envelope_dir=tmp_path / "envelopes",
        )

    monkeypatch.setattr(risk_stress, "MarginStressLab", _factory)

    payload = risk_stress.stress_run(
        profile="paper",
        presets=["covid"],
        input_bundle=None,
        out_dir=None,
        dry_run=True,
        actor="tester",
        runbook_ref="RUN-RISK-01",
    )

    assert payload["status"] == "ok"
    assert payload["report_path"] is None
    assert payload["envelope_path"] is None
    assert payload["results"]["scenario_results"]


def test_stress_compare_threshold_breach(tmp_path):
    envelope_dir = tmp_path / "envelopes"
    envelope_dir.mkdir()
    current = {
        "recommended_thresholds": {"daily_loss": 4.0, "weekly_loss": 8.0},
    }
    previous = {
        "recommended_thresholds": {"daily_loss": 2.0, "weekly_loss": 6.0},
    }
    (envelope_dir / "envelope_20260102.yaml").write_text(
        _dump_yaml(current),
        encoding="utf-8",
    )
    (envelope_dir / "envelope_20260101.yaml").write_text(
        _dump_yaml(previous),
        encoding="utf-8",
    )

    payload = risk_stress.stress_compare(
        against="20260101", threshold=0.5, envelope_dir=envelope_dir
    )

    assert payload["exit_code"] == 1
    assert payload["diff"]


def test_envelope_apply_updates_policy(tmp_path, monkeypatch):
    policy_path = tmp_path / "risk_policy.yaml"
    policy_path.write_text(
        _dump_yaml(
            {
                "profiles": {
                    "paper": {
                        "risk_limits": {"margin_warn": 0.4, "margin_throttle": 0.6},
                        "kill_switch": {"drawdown_threshold_pct": {"daily": 2.5, "weekly": 5.0}},
                    }
                }
            },
        ),
        encoding="utf-8",
    )
    source = tmp_path / "envelope.yaml"
    source.write_text(
        _dump_yaml(
            {
                "recommended_thresholds": {
                    "daily_loss": 2.0,
                    "weekly_loss": 4.0,
                    "margin_warn": 0.35,
                    "margin_throttle": 0.55,
                }
            },
        ),
        encoding="utf-8",
    )
    audit_payloads = []

    def _capture_audit(payload):
        audit_payloads.append(payload)

    monkeypatch.setattr(risk_stress, "_append_audit", _capture_audit)

    payload = risk_stress.envelope_apply(
        profile="paper",
        source=source,
        risk_policy_path=policy_path,
        dry_run=False,
        require_signoff=True,
        signoff="ops@example.com",
    )

    updated = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    limits = updated["profiles"]["paper"]["risk_limits"]
    drawdown = updated["profiles"]["paper"]["kill_switch"]["drawdown_threshold_pct"]
    assert payload["status"] == "ok"
    assert limits["margin_warn"] == 0.35
    assert limits["margin_throttle"] == 0.55
    assert drawdown["daily"] == 2.0
    assert drawdown["weekly"] == 4.0
    assert audit_payloads
