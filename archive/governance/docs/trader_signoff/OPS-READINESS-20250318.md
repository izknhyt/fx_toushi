# Trader Sign-off — OPS-READINESS-20250318

## 1. 対象スコープ
- AC-02: HITL OCO監視 (`reports/validation_log/AC-02_20251117.md`, `reports/performance/paper/sample_orders.parquet`)
- AC-03: Kill Switchトレース (`reports/validation_log/AC-03_20251117.md`, `logs/events/risk.kill_switch.jsonl`)
- AC-04: Resync TTL Drift (`reports/validation_log/AC-04_20251117.md`, `logs/resync/resync_events.jsonl`)
- AC-05: データレイテンシ (`reports/validation_log/AC-05_20251117.md`, `reports/performance/data_latency/20251117.md`)
- AC-06: Audit Chain (`reports/validation_log/AC-06_20251117.md`, `reports/audit/order_trace/TKT-AC06.md`)

## 2. 確認結果
- [x] `pytest -k paper_ticket_oco`, `tradectl ticket monitor --watch 120` のログを確認し、OCO監視Evidenceを取得。
- [x] `tradectl status --history kill-switch --json` が`logs/events/risk.kill_switch.jsonl`を参照することを確認。
- [x] `tradectl resync --since 2024-01-01T00:00:00Z --symbol USDJPY --failover-report` が `logs/resync/resync_events.jsonl` を出力することを確認。
- [x] `tradectl metrics report --kind latency --window 7d --export reports/performance/data_latency/20251117.md` を実施し、AC-05 Evidenceを確認。
- [x] `tradectl audit trace --order TKT-AC06 --export reports/audit/order_trace/TKT-AC06.md` を実施し、Audit Chain証跡を確認。

## 3. サイン
| 役割 | 氏名/イニシャル | サイン日時 | コメント |
| --- | --- | --- | --- |
| Trader Lead | A. Trader | 2025-11-17T14:55Z | AC-02/03/04/05/06 logセットを確認 |
| Ops Manager | Codex Liaison (prep) | 2025-11-17T14:50Z | AC-02/03/04/05/06 Evidence確認 |
| Product Owner | B. Owner | 2025-11-17T15:00Z | Ops readinessサインオフ |
