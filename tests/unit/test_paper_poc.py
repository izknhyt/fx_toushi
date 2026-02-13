from __future__ import annotations

import re
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


def test_simulate_paper_poc_orb_vwap_strategy_smoke(project_root: Path) -> None:
    result = simulate_paper_poc(
        strategy="m1_us_orb_vwap_retest",
        strategy_manifest_path=project_root / "config" / "strategy_manifest.orb_vwap_experiment.yaml",
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
        seed=7,
    )
    assert result.metrics["trades"] >= 0
    assert all(trade.strategy_id == "m1_us_orb_vwap_retest" for trade in result.trades)


def test_simulate_paper_poc_asia_compression_strategy_smoke(project_root: Path) -> None:
    result = simulate_paper_poc(
        strategy="m1_asia_compression_expansion_breakout",
        strategy_manifest_path=project_root
        / "config"
        / "strategy_manifest.asia_compression_expansion_experiment.yaml",
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
        seed=7,
    )
    assert result.metrics["trades"] >= 0
    assert all(trade.strategy_id == "m1_asia_compression_expansion_breakout" for trade in result.trades)


def test_exit_with_cost_applies_adverse_spread_and_slippage() -> None:
    assert _exit_with_cost(price=100.0, direction="long", spread=0.3, slippage=0.2) == 99.5
    assert _exit_with_cost(price=100.0, direction="short", spread=0.3, slippage=0.2) == 100.5


def test_simulate_paper_poc_consumes_multiple_signals(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run_all(*args, **kwargs):  # noqa: ANN002, ANN003
        return [
            SimpleNamespace(
                strategy_id="m1_baseline_donchian_upper_only",
                direction="long",
                level=150.0,
                buffer=0.1,
            ),
            SimpleNamespace(
                strategy_id="m1_us_session_trend_pullback",
                direction="short",
                level=150.0,
                buffer=0.1,
            ),
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
        window_to="2024-02-15",
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
        return [
            SimpleNamespace(
                strategy_id="m1_baseline_donchian_upper_only",
                direction="long",
                level=150.0,
                buffer=0.1,
            )
        ]

    monkeypatch.setattr(paper_poc.StrategyEngine, "run_all", _fake_run_all)

    result = simulate_paper_poc(
        strategy="m1_baseline_donchian_upper_only",
        strategy_manifest_path=project_root / "config" / "strategy_manifest.yaml",
        data_manifest_path=project_root / "reports" / "data_manifest.json",
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        risk_policy_path=project_root / "config" / "risk_policy.yaml",
        window_from="2024-01-01",
        window_to="2024-02-15",
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


def test_export_series_falls_back_to_csv_on_parquet_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    series = pd.Series([1.0, 2.0, 3.0], name="equity")
    target = tmp_path / "series_output.parquet"

    def _raise_parquet(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("parquet writer unavailable")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise_parquet)
    paper_poc._export_series(target, "equity", series)

    assert not target.exists()
    csv_target = target.with_suffix(".csv")
    assert csv_target.exists()


def test_simulate_paper_poc_enforces_entry_time_filters_on_pending_entries(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_run_all(*args, **kwargs):  # noqa: ANN002, ANN003
        return [SimpleNamespace(strategy_id="m1_us_session_trend_pullback", direction="long")]

    monkeypatch.setattr(paper_poc.StrategyEngine, "run_all", _fake_run_all)

    result = simulate_paper_poc(
        strategy="m1_us_session_trend_pullback",
        strategy_manifest_path=project_root / "config" / "strategy_manifest.hybrid_us_experiment.yaml",
        data_manifest_path=project_root / "reports" / "data_manifest.json",
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        risk_policy_path=project_root / "config" / "risk_policy.yaml",
        window_from="2024-01-01",
        window_to="2024-01-03",
        symbols=["USDJPY"],
        spread_pips=0.005,
        slippage_pips=0.0015,
        slippage_std=0.001,
        ttl_bars=1,
        seed=7,
        entry_on_next_bar=True,
    )
    opened_hours = {pd.Timestamp(trade.opened_at).tz_convert("UTC").hour for trade in result.trades}
    assert 20 not in opened_hours
    assert 21 not in opened_hours
    assert 0 not in opened_hours


def test_simulate_paper_poc_enforces_local_direction_filters_on_pending_entries(
    project_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run_all(*args, **kwargs):  # noqa: ANN002, ANN003
        return [SimpleNamespace(strategy_id="m1_us_session_trend_pullback", direction="long")]

    monkeypatch.setattr(paper_poc.StrategyEngine, "run_all", _fake_run_all)

    base_manifest = (
        project_root / "config" / "strategy_manifest.hybrid_us_experiment.yaml"
    ).read_text(encoding="utf-8")
    block = (
        "        blocked_local_direction_windows:\n"
        "          - timezone: \"UTC\"\n"
        "            weekdays: [\"mon\"]\n"
        "            hours: [20]\n"
        "            directions: [\"long\"]\n"
    )
    patched_manifest = re.sub(
        r"(?m)^        blocked_utc_hours:\s*\[[^\]]*\]\n",
        "        blocked_utc_hours: []\n" + block,
        base_manifest,
        count=1,
    )
    manifest_path = tmp_path / "manifest_local_block.yaml"
    manifest_path.write_text(patched_manifest, encoding="utf-8")

    result = simulate_paper_poc(
        strategy="m1_us_session_trend_pullback",
        strategy_manifest_path=manifest_path,
        data_manifest_path=project_root / "reports" / "data_manifest.json",
        feature_config_path=project_root / "config" / "feature_pipeline.yaml",
        risk_policy_path=project_root / "config" / "risk_policy.yaml",
        window_from="2024-01-01",
        window_to="2024-01-03",
        symbols=["USDJPY"],
        spread_pips=0.005,
        slippage_pips=0.0015,
        slippage_std=0.001,
        ttl_bars=1,
        seed=7,
        entry_on_next_bar=True,
    )
    assert result.trades
    opened_utc = [pd.Timestamp(trade.opened_at).tz_convert("UTC") for trade in result.trades]
    monday_20 = [ts for ts in opened_utc if ts.weekday() == 0 and ts.hour == 20]
    assert monday_20 == []
