# RUN-ACC-01: マルチ口座ヘルスチェック対応手順

> **ACカバレッジ**: FR-58, AC-43, AC-51  
> **Runbook版数**: v1.0  
> **最終更新日**: 2025-11-03  
> **最終更新者**: Ops Manager (Doc Maintainer)  
> **仕様参照**: detailed_design_fx_signal_tool_v1.md §29.1-29.2, §47.1; basic_design_fx_signal_tool_v1.md:95-96,256; 要件定義（テンプレ形式）v_1.md:182  
> **運用シナリオID**: TR-31 (Account aggregation readiness)  
> **関連メトリクス/ログ**: metrics/accounts_aggregator.jsonl, metrics/performance_live_guard.jsonl, reports/performance/portfolio/, reports/audit/reconciliation/, reports/ops/aggregator/<date>.md, logs/audit/accounts_*.jsonl  
> **外部資料**: accounts/<broker>/<account_id>.yaml, reports/governance/runbook_inventory_status.json, validation_playbook/AC-43_ops_readiness.md, docs/runbooks/RUN-AUD-02.md, docs/runbooks/RUN-REC-02.md

## 目的
- `AccountAggregatorService`が検知したマージン/残高/データ鮮度アラートに対し、入出力データの健全性とリスク制御を確認し、迅速に是正措置を取る。
- 口座別および統合ポートフォリオのエクスポージャを評価し、Kill SwitchやReduce-Only判定 (`RUN-RISK-07`) への影響を明確にする。
- 対応結果と証跡を`reports/ops/aggregator/<date>.md`へ集約し、Ops Readiness/監査パック/税務帳票に再利用できる形で保管する。

## トリガー
- `tradectl accounts alerts --severity warn`またはCLI Exit code 42でGuarded推奨が提示されたとき。
- `metrics/accounts_aggregator.jsonl`で`free_margin_pct<config.accounts.margin_warn`、`drawdown_pct>config.accounts.drawdown_warn`、`stale_accounts>0`が連続2回記録されたとき。
- `reports/audit/reconciliation/<date>_<broker>.md`で残高差分>0.5Rが検出されたとき（RUN-AUD-02参照）。
- Ops Agendaの`Runbook Reviews`に本Runbookが`status=grace/overdue`として列挙されたとき。

## 責務
- **Ops Manager**: 初動、CLI操作、証跡整理、Ops Worklog登録。
- **Back Office担当**: ステートメント/CSV更新、差分調査、手動調整案の提示。
- **Risk Manager**: Reduce-Only/Kill Switch判断、エクスポージャ閾値の確認。
- **Product Owner**: 重大逸脱時の資本配分/戦略停止判断。

## 手順
1. **アラート内容の把握**
   - `tradectl accounts status --with-positions --json > reports/ops/aggregator/status_<timestamp>.json`で最新スナップショットを取得。
   - `tradectl accounts alerts --severity warn --export-md reports/ops/aggregator/alerts_<date>.md`を実行し、アラート種別・対象口座・推奨Runbookを記録。
   - `metrics/accounts_aggregator.jsonl`から直近24時間を抽出:
     ```console
     poetry run tools/metrics_extract.py --source metrics/accounts_aggregator.jsonl --window 24h --out reports/ops/aggregator/metrics_<date>.md
     ```
2. **データ入力の検証**
   - `accounts/<broker>/<account_id>.yaml`の`update_interval`, `source`を確認し、欠損が疑われる口座で`tradectl accounts ingest --profile <id>`を再実行。手動CSVの場合は`data/account/<broker>/<account_id>/<date>.csv`を最新化。
   - ステートメント整合性は`RUN-AUD-02`に従い、該当日の`reports/audit/reconciliation/`を確認。差分が残る場合は`Runbook`チェックリストを継続。
   - `tradectl accounts aggregate --export-md reports/performance/portfolio/aggregate_<date>.md`で統合指標を再計算し、前回結果と比較。
3. **リスクアクションの決定**
   - `tradectl performance live-guard --strategy <id> --strict`を実行し、口座逸脱が戦略メトリクスへ波及していないか確認 (`RUN-RISK-07`連携)。
   - `tradectl ops agenda --date <next_business_day>`でCriticalタスクに反映されていることを確認し、Kill SwitchまたはReduce-Onlyが必要ならPOへエスカレーション。
   - 追加証跡が必要な場合は`tradectl governance lifecycle simulate --scenario suspension`でWorst-caseを検証し、意思決定ログを`reports/governance/strategy_board/<meeting>.md`に連携。
4. **フォローアップ**
   - `reports/ops/aggregator/<date>.md`テンプレを更新し、アラート内容、対応ステップ、CLIログ、次アクションを記載。
   - Ops Worklogへ`tradectl ops log add --task account_health --duration <min> --notes "alerts=<...>"`で登録。
   - `RUN-REC-02`（差分調査）や`RUN-TAX-01`（Ledger生成）に連動する場合は該当Runbookチェックリストを開始し、リンクを貼付。

## チェックリスト
- [ ] `tradectl accounts alerts`と`status`出力を保存した
- [ ] `metrics/accounts_aggregator.jsonl`の24時間分を抽出し、逸脱傾向を確認した
- [ ] 入力データ（CSV/API）の再取得または`accounts/*.yaml`設定の検証を実施した
- [ ] `tradectl accounts aggregate`の再計算結果を`reports/performance/portfolio/`へ保存した
- [ ] 必要に応じて`RUN-AUD-02`/`RUN-REC-02`の調査を開始し、リンクを記録した
- [ ] Ops Worklogと`reports/ops/aggregator/<date>.md`へ対応内容を記録した
- [ ] Risk/POとの意思決定ログを`reports/governance/strategy_board/`または`reports/validation_log/`へ反映した

## 証跡
- `reports/ops/aggregator/status_<timestamp>.json`
- `reports/ops/aggregator/alerts_<date>.md`, `reports/ops/aggregator/metrics_<date>.md`
- `reports/performance/portfolio/aggregate_<date>.md`
- `reports/audit/reconciliation/<date>_<broker>.md`（該当する場合）
- `metrics/accounts_aggregator.jsonl`
- `logs/audit/accounts_alerts_<timestamp>.jsonl`
- `ops_worklog.jsonl` (`task='account_health'`)

## サインオフ
| 役割 | 氏名/署名 | 日時 |
| --- | --- | --- |
| Ops Manager | | |
| Back Office | | |
| Risk Manager | | |
| Product Owner | | |

## 改訂履歴
| 版 | 日付 | 概要 | 編集者 |
| --- | --- | --- | --- |
| v1.0 | 2025-11-03 | 初版作成（Aggregated account alert対応フロー定義） | Ops Manager |
