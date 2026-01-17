from __future__ import annotations

from pathlib import Path

from src.reporter.generator import ReportGenerator

FIXTURE = Path(__file__).parent / "reports" / "weekly_attribution" / "weekly_attribution.md"


def test_weekly_attribution_snapshot(tmp_path: Path) -> None:
    template = Path("src") / "reporter" / "templates" / "weekly_m1_core_attribution.md"
    report = ReportGenerator().render_weekly_report(
        week="2026-W03",
        template_path=template,
        kpi={"sharpe": 1.1, "max_dd": 0.05, "win_rate": 0.55, "cum_r": 1.2},
        tickets=[
            {
                "guardrails": {
                    "kill_switch": "none",
                    "spread_status": "normal",
                    "reduce_only": False,
                    "auto_execute_forced_off": False,
                },
                "board_mode": "normal",
            }
        ],
        stress_runs=[],
        journal_entries=[],
        extra_context={
            "kill_switch_history": "deferred",
            "spread_cooldown_summary": "deferred",
            "manual_csv_summary": "n/a",
            "data_quality_summary": "deferred",
            "resync_summary": "deferred",
            "risk_summary_status": "disabled",
            "risk_summary": "n/a",
            "funding_summary": "ok",
            "ops_worklog_excerpt": "no entries",
            "benchmark_summary": "deferred",
            "attribution_summary": "\n".join(
                [
                    "- Status: ok",
                    "- Window: 7d",
                    "",
                    "### Summary",
                    "",
                    "- top_pairs: [{'pair': 'USDJPY', 'pnl': 0.1}]",
                    "",
                    "### Highlights",
                    "",
                    "- USDJPY contribution=0.1",
                ]
            ),
        },
    )
    expected = FIXTURE.read_text(encoding="utf-8")
    assert report.strip() == expected.strip()
