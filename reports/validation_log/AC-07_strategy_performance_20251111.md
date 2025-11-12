---
id: AC-07-20251111
requirement: AC-07 Baseline strategy performance
dataset: reports/research/m1_baseline/metrics_20251111.json
hash: b025bf8a5da4337b918844d1c9cd1c1ce617e3e9f169318c246f5975dab73bfc
source: docs/runbooks/STRAT-M1-VALIDATION.md
owner: Quant Lead
reviewer: Product Owner
due_date: 2025-11-18
status: confirmed
fallback_applied: false
fallback_reason: n/a
linked_runbooks:
  - docs/runbooks/STRAT-M1-VALIDATION.md
signal_cycle_snapshot: reports/validation_log/evidence/20251111/ac07_board_snapshot.json
---

## 1. 受入条件
- [x] PF_all ≥ 1.18、Sharpe(OOS) ≥ 0.85、MaxDD(OOS) ≤ 13%
- [x] 95% BCa下限: PF≥1.12、Sharpe≥0.78
- [x] `data_manifest.json::m1_baseline_ma_rsi::2024-12-31` と同一`dataset_hash`

## 2. 証跡
| Artifact | パス | SHA256 | 備考 |
| --- | --- | --- | --- |
| metrics | reports/research/m1_baseline/metrics_20251111.json | b025bf8a5da4337b918844d1c9cd1c1ce617e3e9f169318c246f5975dab73bfc | PF_all=1.2942, Sharpe(OOS)=0.92, MaxDD(OOS)=0.11 |
| Validationノート | reports/research/m1_baseline/validation_20251111.md | bd51a97faee2091333f9cd4b0762556403c1b21c5b86850ad7ff4f9191ce5f89 | Thresholdチェックと差分ログ |

## 3. コメント
- PF_all=1.29で閾値を0.11上回り、OOS Sharpe=0.92/MaxDD=0.11でAC-07条件を満たした。
- Bootstrap CI (PF lower=1.15, Sharpe lower=0.88) もRunbook要求をクリア。

## 4. サイン
| 役割 | 氏名/イニシャル | 日時 |
| --- | --- | --- |
| Quant Lead | QL | 2025-11-11 22:07Z |
| Product Owner | PO | 2025-11-11 22:08Z |
