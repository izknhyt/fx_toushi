from __future__ import annotations

from pathlib import Path

import pytest

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


def test_simulate_paper_poc_tz_aware_feature_matrix(project_root: Path, monkeypatch) -> None:
    import pandas as pd

    from src.features.pipeline import FeaturePipeline

    def _tz_aware_features(self: FeaturePipeline, *, symbol: str, price_df: pd.DataFrame) -> pd.DataFrame:
        ts = pd.to_datetime(price_df["timestamp"])
        idx = ts.dt.tz_localize("UTC") if ts.dt.tz is None else ts.dt.tz_convert("UTC")
        return pd.DataFrame({"tz_feat": 1.0}, index=idx)

    monkeypatch.setattr(FeaturePipeline, "compute_feature_matrix", _tz_aware_features)

    result = simulate_paper_poc(
        strategy_manifest_path=project_root / "config" / "strategy_manifest.yaml",
        data_manifest_path=project_root / "reports" / "data_manifest.json",
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        risk_policy_path=project_root / "config" / "risk_policy.yaml",
        window_from="2025-12-01",
        window_to="2025-12-02",
        spread_pips=0.0,
        ttl_bars=6,
    )
    assert result.metrics["trades"] >= 0


def test_simulate_paper_poc_symbols_override(project_root: Path) -> None:
    result = simulate_paper_poc(
        strategy_manifest_path=project_root / "config" / "strategy_manifest.yaml",
        data_manifest_path=project_root / "reports" / "data_manifest.json",
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        risk_policy_path=project_root / "config" / "risk_policy.yaml",
        window_from="2024-01-01",
        window_to="2024-01-02",
        symbols=["USDJPY"],
        seed=42,
    )
    assert result.metrics["trades"] >= 0


def test_simulate_paper_poc_session_filter_validation(project_root: Path) -> None:
    with pytest.raises(ValueError):
        simulate_paper_poc(
            strategy_manifest_path=project_root / "config" / "strategy_manifest.yaml",
            data_manifest_path=project_root / "reports" / "data_manifest.json",
            feature_config_path=project_root / "config" / "feature_pipeline.yaml",
            risk_policy_path=project_root / "config" / "risk_policy.yaml",
            window_from="2024-01-01",
            window_to="2024-01-02",
            session_start_hour=6,
        )
    with pytest.raises(ValueError):
        simulate_paper_poc(
            strategy_manifest_path=project_root / "config" / "strategy_manifest.yaml",
            data_manifest_path=project_root / "reports" / "data_manifest.json",
            feature_config_path=project_root / "config" / "feature_pipeline.yaml",
            risk_policy_path=project_root / "config" / "risk_policy.yaml",
            window_from="2024-01-01",
            window_to="2024-01-02",
            session_start_hour=25,
            session_end_hour=2,
        )


def test_simulate_paper_poc_trailing_validation(project_root: Path) -> None:
    with pytest.raises(ValueError):
        simulate_paper_poc(
            strategy_manifest_path=project_root / "config" / "strategy_manifest.yaml",
            data_manifest_path=project_root / "reports" / "data_manifest.json",
            feature_config_path=project_root / "config" / "feature_pipeline.yaml",
            risk_policy_path=project_root / "config" / "risk_policy.yaml",
            window_from="2024-01-01",
            window_to="2024-01-02",
            trail_atr_mult=0.0,
        )


def test_simulate_paper_poc_hybrid_allocation_smoke(project_root: Path) -> None:
    result = simulate_paper_poc(
        strategy=None,
        strategy_manifest_path=project_root / "config" / "strategy_manifest.hybrid_us_experiment.yaml",
        data_manifest_path=project_root / "reports" / "data_manifest.json",
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        risk_policy_path=project_root / "config" / "risk_policy.yaml",
        allocation_config_path=project_root / "config" / "strategy_allocation.yaml",
        allocation_profile="hybrid_us_experiment",
        window_from="2024-01-01",
        window_to="2024-01-03",
        symbols=["USDJPY"],
        spread_pips=0.005,
        slippage_pips=0.0015,
        ttl_bars=6,
        seed=7,
    )
    assert result.metrics["trades"] >= 0
    allowed = {"m1_baseline_donchian_upper_only", "m1_us_session_trend_pullback"}
    assert all((trade.strategy_id in allowed) for trade in result.trades)
