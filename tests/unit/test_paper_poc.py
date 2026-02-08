from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.backtest import paper_poc
from src.backtest.paper_poc import (
    RiskProfileSettings,
    StrategyRiskLimits,
    StreakRules,
    _exit_with_cost,
    simulate_paper_poc,
)


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


def test_exit_with_cost_applies_adverse_spread_and_slippage() -> None:
    assert _exit_with_cost(price=100.0, direction="long", spread=0.3, slippage=0.2) == 99.5
    assert _exit_with_cost(price=100.0, direction="short", spread=0.3, slippage=0.2) == 100.5


def test_simulate_paper_poc_consumes_multiple_signals(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run_all(*args, **kwargs):  # noqa: ANN002, ANN003
        return [
            SimpleNamespace(strategy_id="m1_baseline_donchian_upper_only", direction="long"),
            SimpleNamespace(strategy_id="m1_us_session_trend_pullback", direction="short"),
        ]

    monkeypatch.setattr(paper_poc.StrategyEngine, "run_all", _fake_run_all)
    monkeypatch.setattr(
        paper_poc,
        "_load_risk_policy",
        lambda _path, _profile: RiskProfileSettings(
            base_equity=12_000_000.0,
            base_per_trade_pct=0.6,
            streak=StreakRules(),
            per_strategy_limits={
                "m1_baseline_donchian_upper_only": StrategyRiskLimits(
                    per_trade_pct=0.6,
                    max_concurrent_overall=10,
                    max_concurrent_bucket=10,
                ),
                "m1_us_session_trend_pullback": StrategyRiskLimits(
                    per_trade_pct=0.6,
                    max_concurrent_overall=10,
                    max_concurrent_bucket=10,
                ),
            },
            total_risk_soft_pct=None,
            total_risk_hard_pct=None,
            bucket_risk_cap_pct=None,
            r_eff_soft=None,
            r_eff_hard=None,
            corr_group_risk_cap_pct=None,
        ),
    )

    result = simulate_paper_poc(
        strategy=None,
        strategy_manifest_path=project_root / "config" / "strategy_manifest.hybrid_us_experiment.yaml",
        data_manifest_path=project_root / "reports" / "data_manifest.json",
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        risk_policy_path=project_root / "config" / "risk_policy.yaml",
        allocation_config_path=project_root / "config" / "strategy_allocation.yaml",
        allocation_profile="hybrid_us_experiment",
        window_from="2024-01-01",
        window_to="2024-01-02",
        symbols=["USDJPY"],
        spread_pips=0.005,
        slippage_pips=0.0015,
        ttl_bars=1,
        seed=7,
    )
    traded_ids = {trade.strategy_id for trade in result.trades}
    assert "m1_baseline_donchian_upper_only" in traded_ids
    assert "m1_us_session_trend_pullback" in traded_ids


def test_simulate_paper_poc_entry_on_next_bar_uses_next_open(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_run_all(*args, **kwargs):  # noqa: ANN002, ANN003
        return [SimpleNamespace(strategy_id="m1_baseline_donchian_upper_only", direction="long")]

    monkeypatch.setattr(paper_poc.StrategyEngine, "run_all", _fake_run_all)

    result = simulate_paper_poc(
        strategy="m1_baseline_donchian_upper_only",
        strategy_manifest_path=project_root / "config" / "strategy_manifest.yaml",
        data_manifest_path=project_root / "reports" / "data_manifest.json",
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        risk_policy_path=project_root / "config" / "risk_policy.yaml",
        window_from="2024-01-01",
        window_to="2024-01-03",
        symbols=["USDJPY"],
        spread_pips=0.0,
        slippage_pips=0.0,
        slippage_std=0.0,
        ttl_bars=1,
        seed=7,
        entry_on_next_bar=True,
    )
    assert result.trades
    first_trade = result.trades[0]
    price_df = pd.read_parquet(Path(str(result.dataset_path)))
    price_df["timestamp"] = pd.to_datetime(price_df["timestamp"], utc=True)
    opened_at = pd.Timestamp(first_trade.opened_at).tz_convert("UTC")
    opened_row = price_df.loc[price_df["timestamp"] == opened_at]
    assert not opened_row.empty
    assert first_trade.entry == pytest.approx(float(opened_row.iloc[0]["open"]))


def test_simulate_paper_poc_default_seed_is_deterministic(project_root: Path) -> None:
    kwargs = dict(
        strategy="m1_baseline_donchian_upper_only",
        strategy_manifest_path=project_root / "config" / "strategy_manifest.yaml",
        data_manifest_path=project_root / "reports" / "data_manifest.json",
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        risk_policy_path=project_root / "config" / "risk_policy.yaml",
        window_from="2024-01-01",
        window_to="2024-01-05",
        symbols=["USDJPY"],
        spread_pips=0.005,
        slippage_pips=0.0015,
        slippage_std=0.001,
        ttl_bars=6,
    )
    result_a = simulate_paper_poc(**kwargs)
    result_b = simulate_paper_poc(**kwargs)
    assert result_a.seed_used == 0
    assert result_b.seed_used == 0
    assert result_a.metrics == result_b.metrics
