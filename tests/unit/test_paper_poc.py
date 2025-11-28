from __future__ import annotations

from pathlib import Path

from src.backtest.paper_poc import simulate_paper_poc


def test_simulate_paper_poc_smoke(project_root: Path) -> None:
    result = simulate_paper_poc(
        strategy_manifest_path=project_root / "config" / "strategy_manifest.yaml",
        data_manifest_path=project_root / "reports" / "data_manifest.json",
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        risk_policy_path=project_root / "config" / "risk_policy.yaml",
        window_from="2021-01-01",
        window_to="2021-01-05",
        spread_pips=0.0,
        ttl_bars=6,
    )
    assert "pf_all" in result.metrics
    assert result.metrics["trades"] >= 0
