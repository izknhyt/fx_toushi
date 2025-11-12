---
id: AC-05-20250318
requirement: AC-05 Data ingestion throughput
dataset: metrics/data_ingestion_sla.jsonl
hash: bea6afd84c42d8597878aeb6bcd2499ed0c077aaf93faaadecf82f1ca29f3d35
source: docs/runbooks/RUN-DATA-05.md
owner: Data Engineer
reviewer: Ops Manager
due_date: 2025-03-24
status: pending
fallback_applied: false
fallback_reason: n/a
linked_runbooks:
  - docs/runbooks/RUN-DATA-05.md
  - docs/runbooks/RUN-DATA-06.md
signal_cycle_snapshot: reports/validation_log/evidence/20250318/ac05_board_snapshot.json
---

## 1. 受入条件
- [ ] 主要4ペアの5分/1時間足で遅延<100msを計測
- [ ] 同時実行ワーカー数≥4（平均）/最大6を30分保持
- [ ] Catch-up完了ログで30分以内の解消を確認（`tradectl resync --since <ts>`実装後）

## 2. 証跡
| Artifact | パス | SHA256 | 備考 |
| --- | --- | --- | --- |
| SLAログ | metrics/data_ingestion_sla.jsonl | bea6afd84c42d8597878aeb6bcd2499ed0c077aaf93faaadecf82f1ca29f3d35 | サンプル行を追加済み |
| CLIウォッチ | reports/implementation/20250315_pkg-data-status-01/logs/data_status_watch.log | f8d69edce48445abc24769c636c5ef7ea8f67fc61701bd494d5f46c1e8b3fac7 | `tradectl data status --log-stage-eval` 実行ログ |

## 3. コメント
- `tradectl data status --provider yfinance --log-stage-eval --json` を実行し、rate_limit_windowへの記録とCLIログを保存済み。Catch-up演習後に`tradectl resync --since <ts>`の証跡を追加予定。

## 4. CLI証跡
```
$ poetry run python -m tradectl data status --provider yfinance --log-stage-eval --json
{"timestamp": "2025-11-10T14:01:33Z", "providers": ["yfinance"], "watch": false, "log_stage_eval": true, "rate_limit_path": "metrics/rate_limit_window.jsonl", "ingestion_samples": [{"ts": "2025-03-18T00:00:00Z", "provider": "yfinance", "phase": "fetch", "symbol": "USDJPY", "p95_latency_sec": 14.6, "threshold_sec": 18, "status": "ok", "runbook_ref": "RUN-DATA-05", "notes": "stage=hold"}, {"ts": "2025-03-18T00:00:00Z", "provider": "yfinance", "phase": "processing", "symbol": "USDJPY", "p95_latency_sec": 9.8, "threshold_sec": 12, "status": "ok", "runbook_ref": "RUN-DATA-06", "notes": "manual_csv=false"}], "logged_providers": ["yfinance"]}
```

## 4. サイン
| 役割 | 氏名/イニシャル | 日時 |
| --- | --- | --- |
| Data Engineer | | |
| Ops Manager | | |
