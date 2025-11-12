---
id: AC-07-20250318
requirement: AC-07 Baseline strategy performance
dataset: reports/research/m1_baseline/metrics_20250318.json
hash: pending_metrics_not_generated
source: docs/runbooks/STRAT-M1-VALIDATION.md
owner: Quant Lead
reviewer: Product Owner
due_date: 2025-03-24
status: pending
fallback_applied: false
fallback_reason: n/a
linked_runbooks:
  - docs/runbooks/STRAT-M1-VALIDATION.md
signal_cycle_snapshot: reports/validation_log/evidence/20250318/ac07_board_snapshot.json
---

## 1. 受入条件
- [ ] PF_all ≥ 1.18、Sharpe(OOS) ≥ 0.85、MaxDD(OOS) ≤ 13%
- [ ] 95% BCa下限: PF≥1.12、Sharpe≥0.78
- [ ] `data_manifest.json::m1_baseline_ma_rsi::2024-12-31` と同一`dataset_hash`

## 2. 証跡
| Artifact | パス | SHA256 | 備考 |
| --- | --- | --- | --- |
| metrics | reports/research/m1_baseline/metrics_20250318.json | (pending) | |
| Validationノート | reports/research/m1_baseline/validation_20250318.md | (pending) | |

## 3. コメント
- データ生成はQuantチームが担当。Opsレビュー待ち。

## 4. サイン
| 役割 | 氏名/イニシャル | 日時 |
| --- | --- | --- |
| Quant Lead | | |
| Product Owner | | |
