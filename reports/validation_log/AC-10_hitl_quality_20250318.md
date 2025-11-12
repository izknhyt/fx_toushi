---
id: AC-10-20250318
requirement: AC-10 HITL quality
dataset: reports/performance/paper/hitl_trials.csv
hash: pending_hitl_trials_not_recorded
source: docs/runbooks/RUN-HITL-01.md
owner: Ops Manager
reviewer: Product Owner
due_date: 2025-03-24
status: pending
fallback_applied: false
fallback_reason: n/a
linked_runbooks:
  - docs/runbooks/RUN-HITL-01.md
signal_cycle_snapshot: reports/validation_log/evidence/20250318/ac10_board_snapshot.json
---

## 1. 受入条件
- [ ] 提案→承認/却下/編集→ログ保存の100試行で失敗0
- [ ] TTL/ドリフト超過は自動失効
- [ ] Liveステートメントと突合し未整合0

## 2. 証跡
| Artifact | パス | SHA256 | 備考 |
| --- | --- | --- | --- |
| Trial CSV | reports/performance/paper/hitl_trials.csv | (pending) | |
| Slippage集計 | reports/performance/paper/slippage_stats.json | (pending) | |

## 3. コメント
- テスト脚本を`docs/runbooks/RUN-HITL-01.md`へリンク予定。

## 4. サイン
| 役割 | 氏名/イニシャル | 日時 |
| --- | --- | --- |
| Ops Manager | | |
| Product Owner | | |
