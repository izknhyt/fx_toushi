# Command Status (20251111)

| Step | Command | Exit Code |
| --- | --- | --- |
| Step 0 | poetry run pytest -k config_schema_smoke | 0 |
| Step 1 | poetry run python tools/check_dataset_hash.py --manifest reports/data_manifest.json --strategy m1_baseline_ma_rsi | 0 |
| Step 1 | poetry run python tools/verify_parquet.py data/research/curated/usdjpy/usdjpy_m5_20210101_20241231.parquet --expect-frequency 5T | 0 |
| Step 2 | poetry run tradectl backtest run --strategy m1_baseline_ma_rsi --profile paper-m1-baseline --from 2021-01-01 --to 2024-12-31 --export metrics --output reports/research/m1_baseline/metrics_${RUN_DATE}.json | 0 |
| Step 3 | poetry run tradectl backtest run --strategy m1_baseline_ma_rsi --profile paper-m1-baseline --from 2021-01-01 --to 2023-06-30 --out reports/backtest/m1_baseline/is/${RUN_DATE} | 0 |
| Step 3 | poetry run tradectl backtest run --strategy m1_baseline_ma_rsi --profile paper-m1-baseline --from 2023-07-01 --to 2024-12-31 --out reports/backtest/m1_baseline/oos/${RUN_DATE} | 0 |
| Step 3 | poetry run tradectl backtest walk-forward --strategy m1_baseline_ma_rsi --profile paper-m1-baseline --window 6m --step 1m --from 2021-01-01 --to 2024-12-31 --out reports/backtest/m1_baseline/wf/${RUN_DATE} | 0 |
| Step 4 | poetry run python tools/evaluate_metrics.py reports/research/m1_baseline/metrics_${RUN_DATE}.json --baseline reports/research/m1_baseline/metrics_prev.json --out reports/research/m1_baseline/validation_${RUN_DATE}.md | 0 |
| Step 4 | poetry run python tools/check_dataset_hash.py --manifest reports/data_manifest.json --strategy m1_baseline_ma_rsi --write reports/research/m1_baseline/validation_${RUN_DATE}.md --append | 0 |
| Step 5 | poetry run tradectl board --view strategy --save-snapshot reports/validation_log/evidence/${RUN_DATE}/board_snapshot.json | 0 |
| Step 5 | poetry run tradectl status --json > reports/validation_log/evidence/${RUN_DATE}/status_snapshot.json | 0 |
| Step 5 | poetry run tradectl data health --format json > reports/validation_log/evidence/${RUN_DATE}/data_health_${RUN_DATE}.json | 0 |
| Step 5 | poetry run tradectl data ack --dry-run --provider dukascopy > reports/validation_log/evidence/${RUN_DATE}/ack_log.txt | 0 |
