# R-05 Audit Log Compression Plan (Draft)

- Risk ID: R-05 監査ログ肥大化
- Due: 2025-03-29 JST
- Owner: Lead Engineer

## 1. 対象パス
| Directory | Retention | Compression Tool | Notes |
| --- | --- | --- | --- |
| `logs/audit/` | 90 days WORM | `tar -czf` + SHA256 | 週次バッチ予定（日曜 20:00 JST） |
| `reports/audit/` | 180 days | `zip -r` | Evidence添付物向け。 |
| `metrics/*.jsonl` | 30 days sliding | `python tools/metrics_extract.py --prune` | S3移行時に暗号化。 |

## 2. ジョブ設計
1. `poetry run python tools/metrics_extract.py --prune --retention-days 30 --output reports/risk/20250318_prelaunch/prune_preview.json` で影響を可視化。
2. `crontab` に以下を追記（仮）：
   ```
   0 20 * * 0 cd /Users/izumimotohayato/development/codex_invest && make audit-log-archive
   ```
   > `make audit-log-archive` ターゲットは`ci/Makefile`に追加予定。無い場合は手動で`tar -czf logs/audit/archive_<date>.tar.gz logs/audit/*.jsonl`を実行。
3. 成果物のSHA-256を`reports/risk/20250318_prelaunch/log_archive_hashes.md`に追記し、`RUN-AUD-02`のEvidence欄へリンク。

## 3. 未解決タスク
- [ ] `make audit-log-archive` ターゲットを実装。
- [ ] `RUN-AUD-02` へ自動アーカイブ手順を追記。
- [ ] `docs/runbooks/daily_agenda/<date>.md` のFollow-up欄にR-05チェックを追加。

更新があれば`docs/risk_review/20250318_prelaunch.md`のR-05項へ結果を追記してください。
