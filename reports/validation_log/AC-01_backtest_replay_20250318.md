---
id: AC-01-20250318
requirement: AC-01 Backtest reproducibility
dataset: data/research/curated/usdjpy_m5_20210101_20241231.parquet
hash: pending_dataset_not_generated
source: docs/runbooks/STRAT-M1-VALIDATION.md
owner: Quant Lead
reviewer: Ops Manager
due_date: 2025-03-24
status: pending
fallback_applied: false
fallback_reason: n/a
linked_runbooks:
  - docs/runbooks/STRAT-M1-VALIDATION.md
  - docs/runbooks/RUN-DATA-05.md
signal_cycle_snapshot: reports/validation_log/evidence/20250318/ac01_board_snapshot.json
---

## 1. 受入条件
- [ ] `tradectl backtest run --strategy m1_baseline_ma_rsi --from 2021-01-01 --to 2024-12-31` を実行
- [ ] `metrics/research/m1_baseline/*.json` に`dataset_hash`/`config_hash`を保存
- [ ] 再実行時の差分が±0.1%以内であることを`reports/research/m1_baseline/validation_20250318.md`へ記録

## 2. 証跡
| Artifact | パス | SHA256 | 備考 |
| --- | --- | --- | --- |
| Backtestログ | reports/research/m1_baseline/validation_20250318.md | (pending) | CLI貼付 |
| metrics.json | reports/research/m1_baseline/metrics_20250318.json | (pending) | |

## 3. コメント
- データセット未生成のため`hash`は保留。`make data-build m1_baseline`完了後に再計算する。

## 4. サイン
| 役割 | 氏名/イニシャル | 日時 |
| --- | --- | --- |
| Quant Lead | | |
| Ops Manager | | |
