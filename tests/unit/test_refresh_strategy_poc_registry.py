from __future__ import annotations

from tools.refresh_strategy_poc_registry import (
    STRATEGY_CONFIGS,
    classify_strategy_status,
)


def _report(*, avg_r: float, pf: float, count: int, max_dd: float, gate_pass: bool) -> dict:
    return {
        "summary": {"avg_r": avg_r, "pf": pf, "count": count},
        "acceptance_gate": {
            "status": "pass" if gate_pass else "fail",
            "checks": {
                "avg_r_positive": avg_r > 0,
                "pf_min_1_10": pf >= 1.1,
                "max_dd_le_0_30": max_dd <= 0.30,
                "trade_count_ge_300": count >= 300,
            },
        },
    }


def test_strategy_registry_inventory_covers_expected_ids() -> None:
    strategy_ids = {cfg.strategy_id for cfg in STRATEGY_CONFIGS}
    assert strategy_ids == {
        "m1_asia_compression_expansion_breakout",
        "m1_baseline_donchian",
        "m1_baseline_donchian_long_only",
        "m1_baseline_donchian_upper_only",
        "m1_baseline_ma_rsi",
        "m1_us_orb_vwap_retest",
        "m1_us_session_trend_pullback",
    }


def test_classify_strategy_status_returns_win_for_strict_all_and_positive_validation() -> None:
    status = classify_strategy_status(
        lifecycle="production_candidate",
        report_2025=_report(avg_r=0.12, pf=1.4, count=20, max_dd=0.02, gate_pass=False),
        report_all=_report(avg_r=0.05, pf=1.2, count=400, max_dd=0.08, gate_pass=True),
    )
    assert status == "validated_win_production_candidate"


def test_classify_strategy_status_returns_mixed_when_only_validation_is_positive() -> None:
    status = classify_strategy_status(
        lifecycle="satellite_candidate",
        report_2025=_report(avg_r=0.02, pf=1.2, count=30, max_dd=0.03, gate_pass=False),
        report_all=_report(avg_r=-0.01, pf=0.98, count=400, max_dd=0.18, gate_pass=False),
    )
    assert status == "validated_mixed"


def test_classify_strategy_status_marks_research_only_failures() -> None:
    status = classify_strategy_status(
        lifecycle="research_only",
        report_2025=_report(avg_r=-0.03, pf=0.9, count=20, max_dd=0.03, gate_pass=False),
        report_all=_report(avg_r=-0.05, pf=0.8, count=350, max_dd=0.19, gate_pass=False),
    )
    assert status == "validated_fail_research_only"
