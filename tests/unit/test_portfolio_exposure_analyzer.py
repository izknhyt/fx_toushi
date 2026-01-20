from __future__ import annotations

from pathlib import Path

from src.risk.portfolio_exposure import PortfolioExposureAnalyzer


def test_portfolio_exposure_variance_detection(tmp_path: Path) -> None:
    analyzer = PortfolioExposureAnalyzer(
        thresholds_path=tmp_path / "thresholds.yaml",
        metrics_path=tmp_path / "metrics.jsonl",
        audit_log=tmp_path / "audit.jsonl",
    )
    tmp_path.joinpath("thresholds.yaml").write_text(
        "\n".join(
            [
                "schema_version: portfolio_exposure.v1",
                "thresholds:",
                "  margin_utilization_warn: 0.45",
                "  margin_utilization_critical: 0.6",
                "  hedge_ratio_warn: 0.3",
                "  net_r_eff_warn: 0.8",
                "  net_r_eff_critical: 1.2",
                "",
            ]
        ),
        encoding="utf-8",
    )
    state = {
        "total_equity": 1000.0,
        "total_margin_used": 700.0,
        "r_eff_total": 1.3,
        "hedge_ratio": 0.35,
    }
    variances = analyzer.detect_variance(state)
    kinds = {entry["kind"] for entry in variances}
    assert "margin_utilization" in kinds
    assert "net_r_eff" in kinds
