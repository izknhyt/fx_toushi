# UX Feedback Capture Log

- 最終更新日: 2025-03-05
- 運用責任: Opsリード（HITLチーム）
- 作成目的: チケットUX／CLI操作体験に関するフィードバックを単一の証跡に集約し、Release Readiness（§30）とEvidence Graph（§23）で再利用できる形に整える。

## 1. 収集チャネル

### 1.1 チケット承認/却下イベント
- ソース: `logs/audit/ticket.jsonl`（`event=approve|reject`）。
- 取得手順: `tradectl ticket queue --summary --format json`で対象チケットを特定し、`tradectl ticket inspect --id <ticket_id>`でコメントを抽出。
- 記録: `FeedbackItem`（§26.3）に`source='board'`、`tags`には`spread`/`risk`/`ux-copy`等を付与。

### 1.2 CLIパフォーマンス/滞在時間
- ソース: `metrics/cli_perf.jsonl`（Board/Feedback CLIの滞在秒数）。
- 取得手順: `tradectl metrics latency --mode paper --window 1d --format json`を実行し、`command='board'`の`p95`値を抽出。
- 記録: `FeedbackItem.tags`へ`cli-latency`を付与し、`avg_time_to_decision`へ転記。

### 1.3 手動メモ/Runbook注記
- ソース: `docs/runbooks/daily_agenda/notes/<YYYYMMDD>.md`、`RUN-HITL-01`チェックリスト欄。
- 取得手順: 候補メモを抜粋し、再現に必要なRunbook節・スクリーンショットを記録。
- 記録: `source='manual'`として、Runbook参照を`FeedbackItem.recommendation`に添付。

## 2. 記録フォーマット

すべての記録は以下のMarkdownブロック形式で追記する。テンプレ更新は`ChangeLedger.category='feedback'`で記録し、更新日を本書冒頭に反映する。

```markdown
## <YYYY-MM-DD> <slug>
- チケットID: <ticket_id or N/A>
- 戦略ID: <strategy_id>
- ソース: board|cli|manual
- タグ: [spread, ux-copy]
- 重要度: high|medium|low
- 関連Runbook: RUN-HITL-01#<section>, RUN-OPS-04
- 関連Evidence: reports/validation_log/AC-10_<date>.md, metrics/cli_perf.jsonl
- サマリ:
  - 課題: ...
  - 推奨アクション: ...
- Change Ledger: change_id=<id>（未対応の場合は`pending`）
```

## 3. Evidence Graph連携
- Evidenceノード命名: `ux_feedback/<YYYYMMDD>_<slug>`。
- `tradectl feedback export --include-prompts`実行後、`EvidenceGraphService.link_artifact`で`kind='ux_feedback'`として登録。
- リンクするファイル: 本書の該当節、`logs/audit/ticket.jsonl`該当行、`reports/validation_log/AC-10_<date>.md`スクリーンショット参照。
- Change Ledger連携: `ChangeLedger.record_change(category='feedback', evidence_refs=[...])`を必須化。

## 4. Runbook整合チェック
1. `RUN-HITL-01`「Boardレビュー」節のチェックボックスを更新し、本書への追記日と一致しているか確認。
2. `docs/runbooks/daily_agenda/CODEX_DAILY_START.md`の「フィードバック確認」行に`status=done`と追記者署名を残す。
3. `RUN-OPS-04`週次レビューで`tradectl feedback summarize --window 7d`の結果と本書の差分を確認し、欠落があれば本書へ追記。

## 5. Release Readiness/Delivery連携
- Release Readiness (§30) では`open_feedback`に高優先度項目を添付。`priority_score>=70`の項目は必ず`GateCriterion`へリンク。
- Delivery Control Tower (§25) は`tradectl delivery status`実行時に本書の未対応エントリを参照し、`DeliveryAlert.kind='feedback_gap'`を生成。
- エントリ更新時は`tradectl delivery alerts ack --id <alert_id> --note 'ux_feedback updated'`を実施。

## 6. 監査時の運用
- 監査提出物には最新7件のフィードバックを添付し、各項目の対応状況を`docs/templates/degradation_report.md`に倣って表形式に整形。
- 監査チェックリスト: 本書のSHA256、関連Change Ledger ID、Evidence GraphノードIDを`reports/validation_log/AC-10_<date>.md`に追記。

## 7. メンテナンス
- 更新頻度: 日次（Opsレビュー）、週次（Opsレビュー会議）。
- 古いフィードバックをアーカイブする際は`docs/ux_feedback_archive/<YYYY>/`配下へ移動し、本書からリンクを残す。
- 重大UX課題は`docs/change_requests/`でIssue化し、本書に`change_request=<path>`を追記。

---

本ログに追記する前に、Runbook整合とEvidence Graph登録を完了させること。未登録のままRelease Readinessを通過させることは禁止。
