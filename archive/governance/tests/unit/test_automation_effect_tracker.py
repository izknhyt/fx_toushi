from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from src.ops.automation import AutomationEffectDelta, AutomationEffectTracker


def test_automation_effect_emits_metrics_and_audit(tmp_path: Path) -> None:
    tracker = AutomationEffectTracker(
        ledger_path=tmp_path / "automation_effect.jsonl",
        metrics_path=tmp_path / "metrics" / "ops_automation.jsonl",
        audit_path=tmp_path / "logs" / "audit" / "ops_automation.jsonl",
        gain_threshold_min=5,
    )
    entry = tracker.apply(
        AutomationEffectDelta(
            task="automation-task",
            before_min=30,
            after_min=20,
            effective_date=date(2026, 1, 12),
            runbook_ref="RUN-OPS-01",
            evidence=["evidence.md"],
        )
    )
    assert entry.gain_min == 10

    metrics_path = tmp_path / "metrics" / "ops_automation.jsonl"
    metrics_payloads = [json.loads(line) for line in metrics_path.read_text().splitlines()]
    assert metrics_payloads[0]["event"] == "automation.effect_achieved"
    assert metrics_payloads[0]["gain_min"] == 10

    audit_path = tmp_path / "logs" / "audit" / "ops_automation.jsonl"
    audit_payloads = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert audit_payloads[0]["event"] == "audit.ops_automation"
    assert audit_payloads[0]["entry_hash"].startswith("sha256:")


def test_automation_effect_iter_effects(tmp_path: Path) -> None:
    tracker = AutomationEffectTracker(ledger_path=tmp_path / "automation_effect.jsonl")
    tracker.apply(
        AutomationEffectDelta(
            task="effect-a",
            before_min=5,
            after_min=2,
            effective_date=date(2026, 1, 12),
        )
    )
    tracker.apply(
        AutomationEffectDelta(
            task="effect-b",
            before_min=10,
            after_min=1,
            effective_date=date(2026, 1, 12),
        )
    )
    results = list(tracker.iter_effects(task="effect-a"))
    assert len(results) == 1
    assert results[0].task == "effect-a"
