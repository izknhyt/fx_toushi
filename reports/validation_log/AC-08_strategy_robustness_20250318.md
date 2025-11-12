---
id: AC-08-20250318
requirement: AC-08 Strategy robustness (M1.1 preview)
dataset: reports/backtest/m1_baseline/<run_id>/stress_tests.json
hash: TBD
source: docs/runbooks/STRAT-STRESS-01.md
owner: Quant Lead
reviewer: Risk Manager
due_date: 2025-04-30
status: blocked
fallback_applied: false
fallback_reason: Awaiting M1.1 soak
linked_runbooks:
  - docs/runbooks/STRAT-STRESS-01.md
signal_cycle_snapshot: reports/validation_log/evidence/20250318/ac08_board_snapshot.json
---

## 1. 受入条件
- [ ] Regime別セグメントの取引数 ≥ 45、`PF_segment ≥ 1.05`
- [ ] スプレッド/滑り±50%シナリオで`PF_segment`中央値 ≥ 1.0
- [ ] `strategy_manifest.yaml::stress.validated_at`を更新

## 2. コメント
- M1.1タスクのためblocked扱い。データセット準備後に更新する。

## 3. サイン
| 役割 | 氏名/イニシャル | 日時 |
| --- | --- | --- |
| Quant Lead | | |
| Risk Manager | | |
