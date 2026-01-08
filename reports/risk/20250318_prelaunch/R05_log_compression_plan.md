# R-05 Audit Log Compression Plan (Draft)

- Risk ID: R-05 監査ログ肥大化
- Due: 2025-03-29 JST
- Owner: Lead Engineer

## 0. 免除判断（個人用途）
- Status: waived
- Rationale: 個人用途・ローカル運用のため監査ログ肥大化リスクは許容範囲。外部提供・複数運用者・自動ライブ運用へ移行する場合は再開する。
- Decision date: 2026-01-08

## 1. 対象パス
| Directory | Retention | Compression Tool | Notes |
| --- | --- | --- | --- |
| `logs/audit/` | waived | n/a | 免除 |
| `reports/audit/` | waived | n/a | 免除 |
| `metrics/*.jsonl` | waived | n/a | 免除 |

## 2. ジョブ設計
1. `poetry run python tools/metrics_extract.py --prune --retention-days 30 --output reports/risk/20250318_prelaunch/prune_preview.json` で影響を可視化。
2. `crontab` に以下を追記（仮）：
   ```
   0 20 * * 0 cd /Users/izumimotohayato/development/codex_invest && make audit-log-archive
   ```
   > `make audit-log-archive` ターゲットは`ci/Makefile`に追加予定。無い場合は手動で`tar -czf logs/audit/archive_<date>.tar.gz logs/audit/*.jsonl`を実行。
3. 成果物のSHA-256を`reports/risk/20250318_prelaunch/log_archive_hashes.md`に追記し、`RUN-AUD-02`のEvidence欄へリンク。

## 3. 未解決タスク
- [x] 免除（個人用途のため実施対象外）。

更新があれば`docs/risk_review/20250318_prelaunch.md`のR-05項へ結果を追記してください。
