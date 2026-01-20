from __future__ import annotations

from pathlib import Path

from src.risk.stress_lab import MarginStressLab, StressInputBundle


def _write_policy(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "profiles:",
                "  m1_baseline:",
                "    risk_limits:",
                "      margin_warn: 0.45",
                "      margin_throttle: 0.6",
                "    kill_switch:",
                "      drawdown_threshold_pct:",
                "        daily: 2.5",
                "        weekly: 5.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_presets(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "schema_version: margin_stress_presets.v1",
                "presets:",
                "  - id: demo",
                "    kind: historical",
                "    shock_profile:",
                "      drawdown_pct: 6.0",
                "      weekly_drawdown_pct: 7.0",
                "      margin_peak: 0.7",
                "      r_eff_peak: 2.2",
                "      loss_streak: 5",
                "      corr_hotness: 0.9",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_margin_stress_lab_run(tmp_path: Path) -> None:
    policy_path = tmp_path / "config" / "risk_policy.yaml"
    presets_path = tmp_path / "config" / "risk" / "margin_stress_presets.yaml"
    _write_policy(policy_path)
    _write_presets(presets_path)

    lab = MarginStressLab(
        policy_path=policy_path,
        presets_path=presets_path,
        metrics_path=tmp_path / "metrics" / "margin_stress.jsonl",
        audit_log=tmp_path / "logs" / "audit" / "margin_stress.jsonl",
        envelope_dir=tmp_path / "reports" / "risk" / "envelopes",
    )
    policy = lab.load_policy("m1_baseline")
    scenarios = lab.generate_scenarios(policy, presets=["demo"])
    bundle = StressInputBundle(
        account_state_snapshot=None,
        position_book=None,
        signal_history=None,
        vol_surface=None,
        correlation_matrix=None,
        margin_schedule=None,
    )
    result = lab.run(bundle, scenarios, profile="m1_baseline", actor="tester", runbook_ref="RUN-RISK-01")
    assert result.envelope.profile == "m1_baseline"
    assert result.scenario_results[0].kill_switch_recommendation == "soft_stop"
