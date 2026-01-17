from __future__ import annotations

from pathlib import Path

from src.governance.model_risk import ModelRiskRegisterService


def test_model_risk_register_load(tmp_path: Path) -> None:
    register_path = tmp_path / "model_risk_register.md"
    register_path.write_text(
        "\n".join(
            [
                "---",
                "schema_version: model_risk_register.v1",
                "review_cycle_days: 90",
                "---",
                "",
                "# Model Risk Register",
                "",
                "## Register",
                "",
                "| strategy_id | version | risk_level | status | next_review_due | last_reviewed_by | evidence_refs | watchlist |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
                "| alpha | 0.1.0 | low | approved | 2026-01-01 | reviewer | reports/model_risk/alpha/shap.png | true |",
                "| beta | 0.2.0 | high | blocked | 2026-02-01 | ops |  | false |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    service = ModelRiskRegisterService()
    register = service.load(register_path)

    assert register.metadata["schema_version"] == "model_risk_register.v1"
    assert len(register.entries) == 2
    assert register.entries[0].strategy_id == "alpha"
    assert register.entries[0].watchlist is True
    assert register.entries[1].risk_level == "high"
