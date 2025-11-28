# PoC KPI - m1_baseline_donchian (2024Q1 run, synthetic OHLCV)

- コマンド: `poetry run tradectl backtest poc-paper --strategy m1_baseline_donchian --profile m1_baseline --from 2024-01-01 --to 2024-03-31 --spread 0.01 --ttl-bars 12 --output reports/validation_log/poc_donchian.json`
- データ: `data/research/curated/usdjpy/usdjpy_m5_20240101_20240331_synth.parquet`（5m合成OHLCV。ウォッチリスト他ペアも合成データ準備済）
- KPI: PF_all=2.0082（目標≥1.20 OK）、WinRate=60.49%（目標≥42% OK）、MaxDD=16.91%（目標≤9% NG）、AvgR=0.4595（目標≥1.8 NG）、Trades=777（目標≥12 OK）
- 判定: **保留（合成データ由来で変動大。MaxDD/AvgR未達、実データで再評価必須）**
- エビデンス: `reports/validation_log/poc_donchian.json`
