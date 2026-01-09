"""Integration checks for the weekly reporter template contract."""

from __future__ import annotations

import re
from pathlib import Path


def _load_template(project_root: Path) -> str:
    template_path = project_root / "reports/weekly/templates/m1_core.md"
    return template_path.read_text(encoding="utf-8")


def _extract_section(content: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)"
    match = re.search(pattern, content, flags=re.MULTILINE | re.DOTALL)
    assert match, f"Section '## {heading}' not found in weekly template"
    return match.group("body").strip()


def test_weekly_template_live_guard_section(project_root: Path) -> None:
    """Live Guard table should retain the contract required by risk governance."""

    content = _load_template(project_root)
    section = _extract_section(content, "Live Guard Watch")

    expected_table = "\n".join(
        [
            "| Metric | Value | Threshold | State | Notes |",
            "| --- | --- | --- | --- | --- |",
            (
                "| PF trailing | {{live_guard.pf_trailing.value}} | "
                "{{live_guard.pf_trailing.threshold}} | "
                "{{live_guard.pf_trailing.state}} | {{live_guard.pf_trailing.note}} |"
            ),
            (
                "| Sharpe trailing | {{live_guard.sharpe_trailing.value}} | "
                "{{live_guard.sharpe_trailing.threshold}} | "
                "{{live_guard.sharpe_trailing.state}} | {{live_guard.sharpe_trailing.note}} |"
            ),
            (
                "| Latency p75 | {{live_guard.latency_p75.value}} | "
                "{{live_guard.latency_p75.threshold}} | "
                "{{live_guard.latency_p75.state}} | {{live_guard.latency_p75.note}} |"
            ),
            (
                "| Alerts | {{live_guard.alerts}} | - | {{live_guard.status}} | "
                "{{live_guard.recommended_action}} |"
            ),
        ]
    )

    assert expected_table in section

    for placeholder in (
        "{{live_guard.pf_trailing.value}}",
        "{{live_guard.sharpe_trailing.threshold}}",
        "{{live_guard.latency_p75.note}}",
        "{{live_guard.recommended_action}}",
    ):
        assert placeholder in section


def test_weekly_template_hitl_sections_present(project_root: Path) -> None:
    """Ensure weekly template keeps the HITL evidence and commentary scaffolds."""

    content = _load_template(project_root)

    ops_checklist = _extract_section(content, "Ops Evidence Checklist")
    assert (
        "`tradectl performance live-guard --strategy {{strategy_id}} --window 4w --mode {{mode}} "
        "--output json --strict --save reports/weekly/evidence/{{report_week}}/live_guard.json`"
    ) in ops_checklist

    signal_cycle = _extract_section(content, "Signal Cycle Evidence")
    assert (
        "| Live Guard result | `reports/weekly/evidence/{{report_week}}/live_guard.json` | Risk | "
        "`tradectl performance live-guard --strategy {{strategy_id}} --strict` |"
    ) in signal_cycle

    manual_commentary = _extract_section(content, "Manual Commentary")
    assert "### A/Bテスト結果（担当: Quant Lead / 締切: 日曜 18:00 JST）" in manual_commentary
    assert "### 次週ToDo（担当: Ops Manager / 締切: 月曜 08:30 JST）" in manual_commentary
