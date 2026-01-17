# RUN-JOURNAL-01: Trade Journal 週次レビュー運用

> **ACカバレッジ**: AC-37  
> **Runbook版数**: v0.2  
> **最終更新日**: 2026-01-15  
> **最終更新者**: Codex Liaison (Ops Manager代理)

## 目的
- Trade Journal（承認チケット/実績/コメント）を週次レビューへ反映し、改善タスクへ繋げる。
- `reports/journal/<week>.md` と `metrics/trade_journal.jsonl` の証跡を揃え、監査とValidationに耐えるログを残す。

## 適用範囲・トリガー
- **週次レビュー前（JST 日曜）**: Journal統計/レビュー出力を作成。
- **HITL運用の変更後**: 週次レビューの差分確認を追加。

## 事前準備
- Feature Flag `journal.enabled` / `journal.weekly_summary` が対象プロファイルで有効。
- `logs/journal/journal_entries.db` に書き込み権限があること。

### Feature Flag有効化
1. `config/feature_flags.yaml` の対象プロファイルで `journal.enabled: true` を設定。
2. 同じプロファイルで `journal.weekly_summary: true` を設定。
3. `tradectl report weekly --profile <profile> --week <YYYY-WW> --dry-run` で反映確認。

## 手順

### 1. 日次コメントの入力
1. チケット承認時に `tradectl journal add --ticket-id <id> --user <name> --note "<comment>"` を実行。
2. 追記コメントが必要な場合は `tradectl journal add-note --ticket-id <id> --author <name> --note "<comment>"` を実行。
3. 監査ログ `logs/audit/journal_<YYYYMMDD>.jsonl` の追記を確認。

### 2. 週次レビューの出力
1. 対象週の一覧を確認: `tradectl journal list --week <YYYY-WW> --json`。
2. 週次レビューを出力: `tradectl journal review --week <YYYY-WW> --include-notes --export reports/journal/<YYYY-WW>.md`。
3. 週次レポートを生成: `tradectl report weekly --profile m1 --week <YYYY-WW>`。

### 3. KPI/統計の確認
1. 直近90日の集計: `tradectl journal stats --window 90d --by strategy_id`。
2. `metrics/trade_journal.jsonl` に `win_rate_by_strategy` / `avg_slippage_pips` が出力されていることを確認。

### 4. Validation Playbook更新
1. `docs/validation_playbook/AC37_journal.yaml` に実施記録を追記。
2. `reports/validation_log/AC-37_<date>.md` にレビュー議事とTODOを記録。

## チェックリスト
- [ ] `journal.enabled` / `journal.weekly_summary` が有効
- [ ] `reports/journal/<YYYY-WW>.md` が生成されている
- [ ] `metrics/trade_journal.jsonl` に週次サマリが追記されている
- [ ] `logs/audit/journal_<YYYYMMDD>.jsonl` の更新を確認した
- [ ] `docs/validation_playbook/AC37_journal.yaml` を更新した

## エスカレーション
- Journal出力が空のまま: `journal.enabled` の有効化を確認し、`RUN-FEATURE-FLAG-01` に従い復旧する。
- 監査ログ未更新: DB書き込み権限を確認し、`RUN-OPS-LOG-01` でログ連携を再確認する。

## 履歴更新手順
- Runbook更新時はバージョン番号を+0.1し、最終更新日と更新者を最新化する。
- 変更内容を`reports/governance/runbook_changelog.md`に記録する。
