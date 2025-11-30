# PoC KPI - m1_baseline_ma_rsi (2024 Full-year, Dukascopy clean)

- コマンド: `python - <<'PY'\nfrom pathlib import Path\nfrom src.interfaces.cli.backtest import run_paper_poc\npayload = run_paper_poc(\n    strategy=\"m1_baseline_ma_rsi\",\n    profile=\"m1_baseline\",\n    window_from=\"2024-01-01\",\n    window_to=\"2024-12-31\",\n    spread_pips=0.01,\n    target_r=1.6,\n    ttl_bars=10,\n    risk_policy_path=Path(\"config\")/\"risk_policy.yaml\",\n    data_manifest_path=Path(\"reports\")/\"data_manifest.json\",\n    feature_config_path=Path(\"config\")/\"feature_pipeline.yaml\",\n    strategy_manifest_path=Path(\"config\")/\"strategy_manifest.yaml\",\n    output=None,\n)\nprint(payload[\"metrics\"])\nPY`
- データ: `data/research/curated/usdjpy/usdjpy_m5_20240101_20241231_dukascopy_clean.parquet`（USDJPY 5m 2024、スケール正規化済み）
- KPI: PF_all=0.8295（目標≥1.30 NG）、WinRate=45.85%（目標≥48% NG）、MaxDD=30.12%（目標≤8% NG）、AvgR=-0.0388（目標≥1.6 NG）、Trades=1289（目標≥30 OK）
- 判定: **NG（主要KPI未達。トレード過多かつ損益効率が低いため、シグナル間引き/SL・TP再設計が必要）**
- エビデンス: 再実行ログ未保存（上記コマンドで再取得可）
