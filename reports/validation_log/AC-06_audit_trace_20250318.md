---
id: AC-06-20250318
requirement: AC-06 Audit traceability
dataset: logs/audit/hitl/*.jsonl
hash: pending_audit_trace_not_recorded
source: docs/runbooks/RUN-HITL-01.md
owner: Ops Manager
reviewer: Compliance Advisor
due_date: 2025-03-24
status: pending
fallback_applied: false
fallback_reason: n/a
linked_runbooks:
  - docs/runbooks/RUN-HITL-01.md
  - docs/runbooks/GOV-AUD-01.md
signal_cycle_snapshot: reports/validation_log/evidence/20250318/ac06_board_snapshot.json
---

## 1. 受入条件
- [ ] 任意注文の意思決定経路（シグナル→リスク→執行）を`logs/audit/*.jsonl`から追跡
- [ ] `tradectl ticket export --format json`で取得したデータと一致
- [ ] `reports/validation_log/AC-06_audit_trace_20250318.md` に手順を記録

## 2. 証跡
| Artifact | パス | SHA256 | 備考 |
| --- | --- | --- | --- |
| HITLログ | logs/audit/hitl/ticket_trace_20250318.jsonl | (pending) | |
| Export | reports/implementation/20250315_pkg-ticket-builder-01/evidence/ticket_trace.json | (pending) | |

## 3. コメント
- CLI未実装部分は手動ログで仮埋め予定。

## 4. サイン
| 役割 | 氏名/イニシャル | 日時 |
| --- | --- | --- |
| Ops Manager | | |
| Compliance Advisor | | |
