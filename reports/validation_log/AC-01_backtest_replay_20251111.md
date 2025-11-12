---
id: AC-01-20251111
requirement: AC-01 Backtest reproducibility
dataset: data/research/curated/usdjpy/usdjpy_m5_20210101_20241231.parquet
hash: c2767c1b16d1ed5cde9dde93efa4309cf34f8ad53389cbeec0a8609cf1ca57d6
source: docs/runbooks/STRAT-M1-VALIDATION.md
owner: Quant Lead
reviewer: Ops Manager
due_date: 2025-11-18
status: confirmed
fallback_applied: false
fallback_reason: n/a
linked_runbooks:
  - docs/runbooks/STRAT-M1-VALIDATION.md
  - docs/runbooks/RUN-DATA-05.md
signal_cycle_snapshot: reports/validation_log/evidence/20251111/board_snapshot.json
---

## 1. 受入条件
- [x] `tradectl backtest run --strategy m1_baseline_ma_rsi --from 2021-01-01 --to 2024-12-31` を実行
- [x] `reports/research/m1_baseline/metrics_20251111.json` に`dataset_hash`/`config_hash`を保存
- [x] 再実行時の差分が±0.1%以内であることを`reports/research/m1_baseline/validation_20251111.md`へ記録

## 2. 証跡
| Artifact | パス | SHA256 | 備考 |
| --- | --- | --- | --- |
| Validation note | reports/research/m1_baseline/validation_20251111.md | bd51a97faee2091333f9cd4b0762556403c1b21c5b86850ad7ff4f9191ce5f89 | CLI, dataset hash diffを記録 |
| metrics.json | reports/research/m1_baseline/metrics_20251111.json | b025bf8a5da4337b918844d1c9cd1c1ce617e3e9f169318c246f5975dab73bfc | `tradectl backtest run --export metrics` |

## 3. コメント
- ManifestとファイルのSHA256が一致したため`RUN-DATA-05`ボードガードを解除。PF/Sharpe差分は±0.04以内。

## 4. サイン
| 役割 | 氏名/イニシャル | 日時 |
| --- | --- | --- |
| Quant Lead | QL | 2025-11-11 22:05Z |
| Ops Manager | OM | 2025-11-11 22:06Z |
