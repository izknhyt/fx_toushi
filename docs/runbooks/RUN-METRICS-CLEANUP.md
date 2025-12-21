# RUN-METRICS-CLEANUP: Metrics ログの定期清掃

目的: `metrics/raw` の raw 観測ログを 60 日で gzip、90 日で削除し、`metrics/data_ingestion_sla.jsonl` を 120 日で削除する。

## 推奨スケジュール
- 実行: 毎日 03:00
- ユーザー: `metrics/` 配下に読み書き権限を持つアプリユーザー

## 設定手順（cron）
```
0 3 * * * cd /path/to/codex_invest && /bin/bash tools/cleanup_metrics.sh
```
- `chmod +x tools/cleanup_metrics.sh` を確認。
- `ROOT_DIR` を変えたい場合は引数で指定: `tools/cleanup_metrics.sh /path/to/codex_invest`

## 期待動作
- `metrics/raw/*.jsonl` を 60 日経過で gzip、90 日経過の `.jsonl.gz` を削除
- `metrics/data_ingestion_sla.jsonl*` を 120 日経過で削除

## 運用メモ
- 週次で容量確認する場合は `du -sh metrics metrics/raw` を併せてジョブ化してもよい。
- エラー時は cron のメール通知か、ジョブログで確認。必要に応じて権限を見直す。
