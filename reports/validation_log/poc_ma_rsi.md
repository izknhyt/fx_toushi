# PoC KPI - m1_baseline_ma_rsi (2024Q1 run, synthetic OHLCV)

- コマンド: `poetry run tradectl backtest poc-paper --strategy m1_baseline_ma_rsi --profile m1_baseline --from 2024-01-01 --to 2024-03-31 --spread 0.01 --ttl-bars 12 --output reports/validation_log/poc_ma_rsi.json`
- データ: `data/research/curated/usdjpy/usdjpy_m5_20240101_20240331_synth.parquet`（5m合成OHLCV。ウォッチリスト他ペアも合成データ準備済）
- KPI: PF_all=1.4529（目標≥1.30 OK）、WinRate=55.38%（目標≥48% OK）、MaxDD=5.12%（目標≤8% OK）、AvgR=0.0941（目標≥1.6 NG）、Trades=780（目標≥30 OK）
- 判定: **保留（合成データのため参考値。実データ投入後に再評価必須）**
- エビデンス: `reports/validation_log/poc_ma_rsi.json`
