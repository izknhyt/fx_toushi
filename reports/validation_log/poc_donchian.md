# PoC KPI - m1_baseline_donchian (2024 Full-year, Dukascopy clean)

- コマンド: `python - <<'PY'\nfrom pathlib import Path\nfrom src.interfaces.cli.backtest import run_paper_poc\npayload = run_paper_poc(\n    strategy=\"m1_baseline_donchian\",\n    profile=\"m1_baseline\",\n    window_from=\"2024-01-01\",\n    window_to=\"2024-12-31\",\n    spread_pips=0.01,\n    target_r=1.6,\n    ttl_bars=10,\n    risk_policy_path=Path(\"config\")/\"risk_policy.yaml\",\n    data_manifest_path=Path(\"reports\")/\"data_manifest.json\",\n    feature_config_path=Path(\"config\")/\"feature_pipeline.yaml\",\n    strategy_manifest_path=Path(\"config\")/\"strategy_manifest.yaml\",\n    output=None,\n)\nprint(payload[\"metrics\"])\nPY`
- データ: `data/research/curated/usdjpy/usdjpy_m5_20240101_20241231_dukascopy_clean.parquet`（USDJPY 5m 2024、スケール正規化済み、1d Donchianフォールバック有効）
- KPI: PF_all=2.1844（目標≥1.20 OK）、WinRate=67.64%（目標≥42% OK）、MaxDD=5.77%（目標≤9% OK）、AvgR=0.3646（目標≥1.8 NG）、Trades=445（目標≥12 OK）
- 判定: **部分達成（PF/WinRate/MaxDDは目標クリア、AvgRのみ未達。TP設計とポジ縮小ロジックの改善余地あり）**
- エビデンス: 再実行ログ未保存（上記コマンドで再取得可）
