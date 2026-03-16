from __future__ import annotations

import json
from pathlib import Path

from tools.sweep_long_horizon_fast_lane import _load_cases, _render_summary_md


def test_load_cases_supports_mapping_payload(tmp_path: Path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(
        "\n".join(
            [
                "baseline:",
                '  note: "base"',
                "  strategy_overrides: {}",
                "quality2:",
                '  note: "quality gate"',
                "  strategy_overrides:",
                "    m1_baseline_donchian_upper_only:",
                "      parameters:",
                "        entry:",
                "          filters:",
                "            min_quality_score: 2.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cases = _load_cases(path)

    assert [case.case_id for case in cases] == ["baseline", "quality2"]
    assert cases[1].strategy_overrides["m1_baseline_donchian_upper_only"]["parameters"]["entry"]["filters"]["min_quality_score"] == 2.0


def test_render_summary_md_lists_case_rows() -> None:
    payload = {
        "generated_at_utc": "2026-03-15T13:00:00+00:00",
        "strategy_id": "m1_baseline_donchian_upper_only",
        "selected_windows": ["2016_2025", "2016_2021"],
        "cases": [
            {
                "case_id": "baseline",
                "note": "base",
                "results": [
                    {"window_name": "2016_2025", "summary": {"pf": 1.16, "avg_r": 0.08}},
                    {"window_name": "2016_2021", "summary": {"pf": 0.92, "avg_r": -0.04}},
                ],
            },
            {
                "case_id": "quality2",
                "note": "quality gate",
                "results": [
                    {"window_name": "2016_2025", "summary": {"pf": 1.24, "avg_r": 0.13}},
                    {"window_name": "2016_2021", "summary": {"pf": 0.99, "avg_r": -0.00}},
                ],
            },
        ],
    }

    rendered = _render_summary_md(payload)

    assert "Long-Horizon Fast Lane Sweep" in rendered
    assert "quality2" in rendered
    assert "1.24" in rendered
    assert "quality gate" in rendered
