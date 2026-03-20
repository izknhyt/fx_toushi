from __future__ import annotations

from tools.build_historical_allocation_summary import (
    render_summary_md,
    synthesize_admission_records,
)


def test_synthesize_admission_records_carries_candidate_and_decision_fields() -> None:
    records = synthesize_admission_records(
        ts="2026-03-17T13:10:00Z",
        symbol="USDJPY",
        candidate_trades=[
            {
                "candidate_id": "cand-alpha",
                "strategy_id": "alpha",
                "symbol": "USDJPY",
                "side": "long",
                "confidence": 0.8,
                "quality_score": 1.2,
                "portfolio_group": "usd_jpy_breakout",
                "exposure_bucket": "usd_jpy_breakout_long",
            }
        ],
        admission_outcomes=[
            {
                "strategy_id": "alpha",
                "decision": "accept",
                "reason_code": "selected",
                "portfolio_group": "usd_jpy_breakout",
                "exposure_bucket": "usd_jpy_breakout_long",
            }
        ],
    )

    assert len(records) == 1
    record = records[0]
    assert record["event"] == "portfolio.admission"
    assert record["candidate_id"] == "cand-alpha"
    assert record["candidate"]["strategy_id"] == "alpha"
    assert record["allocation_decision"]["decision"] == "accept"
    assert record["quality_score"] == 1.2


def test_render_summary_md_lists_winner_review_rows() -> None:
    payload = {
        "generated_at_utc": "2026-03-17T13:10:00Z",
        "symbol": "USDJPY",
        "start": "2022-01-01",
        "end": "2025-12-31",
        "stride": 12,
        "rows_evaluated": 10,
        "rows_with_outcomes": 2,
        "admission_event_count": 4,
        "winner_review_summary": [
            {
                "winner_strategy_id": "m1_asia",
                "share_pct": 66.7,
                "count": 4,
                "suggested_action": "review_role_priority",
                "top_reason_code": "tie_break_lost",
            }
        ],
    }

    rendered = render_summary_md(payload)

    assert "Historical Allocation Summary" in rendered
    assert "m1_asia" in rendered
    assert "review_role_priority" in rendered
