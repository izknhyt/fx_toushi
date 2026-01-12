# Codex PR & Review Templates

Codex実装依頼時に利用するPR本文・Packetチェックリスト・受入/レビュー記録テンプレートを集約する。詳細設計書では参照のみとし、更新は本ファイルを変更することで管理する。

## 1. Packetチェックリスト（Codex向け共通テンプレ）
- **設計整合**: 対象セクション引用、I/O契約、例外、Feature Flag初期値をIssue本文にコピペ。差分がある場合は本書更新→再レビュー。
- **テスト指示**: `pytest`コマンド、CLIスナップショット、必要なダミーデータ生成コマンドを列挙。Codexが実行困難な外部依存（SMTP等）は`--skip-smtp`等のオプションを用意し、テスト結果に`SKIP`が出る想定を明示する。
- **戦略マニフェスト**: 戦略の有効化/順序/重みを変更するPacketは`strategy_manifest.yaml`差分を明記し、`strategies.<id>.enabled|priority|weight|feature_flags`の更新値と§3.5/§4.4/§6.7（Config Governance）参照先をPR本文に記載する。CodexはManifestを単一情報源とみなし、他ファイルへの重複定義を禁止。
- **監査ログ検証**: `pytest -k audit_snapshot`など監査ログをファイル比較するテストを定義し、Codexには出力例を提供する。`git diff logs/audit`があれば差戻し。
- **UX確認**: トレーダーはCLIスクリーンショットと`tradectl status`出力をレビュー。`docs/trader_signoff/<packet>.md`テンプレに沿って(1) 画面キャプチャ、(2) 操作所要時間、(3) コメントを記入する。
- **Rollback手順**: 各Packetで変更した設定/Flag/データを明記。例: `cfg change: config/profile_live.yaml (feature_flags.risk_disclosure_enforce)` → `git checkout -- config/profile_live.yaml`で戻す。データ生成の場合は削除コマンドも記載。
- **Configスキャフォールト**: `CONFIG-SCAFF-01`適用済み前提。設定を追加・変更するPacketは`poetry run schema-validate ...`ログをPR本文へ貼付し、必要に応じて`make config-init`の差分を更新する。欠落している雛形が判明した場合は§0.6.12を参照して追加。
- **DocOps同期**: `make check-doc-sync`を実行してRunbook/設計書の差分が反映されていることを確認する。差分が無い場合は`docs/development_plan.md`のBacklog/Update LogへTODOを起票し、RUN-POST-03の「欠損時のエスカレーション」に従う（CIの`python_smoke`ジョブでも同チェックが実行される）。
- **新規CLI**: `tradectl execution recalibrate` / `tradectl scoring diagnostics` / `tradectl kill-switch review`を利用するPacketは、サンプル実行ログと生成物パス（`config/execution_model.calib.yaml`, `reports/diagnostics/scoring_<date>.md`, `reports/audit/kill_switch_review/<ts>.md`）を添付し、Runbook更新との整合を明記する。
- **テンプレ同期**: ReporterやValidationテンプレを変更した場合は`reports/weekly/templates/m1_core.md`・`docs/validation_log/templates/weekly.md`・`docs/trader_signoff/TEMPLATE.md`の差分をPacketに含め、`pytest -k weekly_report_template`・`pytest -k validation_log_template`ログを添付する。
- **初期テンプレート位置と保守責任**: 旧Implementation Packet/Prompt Packageは`docs/archive/`配下に保管（legacy）。現行の進捗管理は`docs/development_plan.md`に集約する。
- **Runbook整合 (Governance/Finance)**: Manifest/Strategy Lifecycle/ガバナンス差分は`docs/runbooks/GOV-STRAT-01.md`、口座ヘルス/ステートメント突合/Ledger/税務差分は`docs/runbooks/RUN-ACC-01.md`・`RUN-AUD-02.md`・`RUN-REC-02.md`・`RUN-TAX-01.md`を更新し、PR本文に該当Runbookと証跡パス（`reports/governance/runbook_inventory_status.json`, `reports/audit/reconciliation/*.md`, `reports/tax/*.md` など）を明示する。

## 2. トレーダー受入試験テンプレ
| チェック項目 | 詳細 | 実施者 | 証跡 |
| --- | --- | --- | --- |
| A1 CLIレンダリング | `tradectl board --guarded`表示をスクリーンショット化し、RiskDisclosureバナー/Spreadバッジを確認 | トレーダー | `docs/trader_signoff/EP04-P1.md`に画像貼付 |
| A2 Ops Worklog | 新コマンド実行後に`ops_worklog.jsonl`へ記録されているか確認 | 運用担当 | JSON抜粋をテンプレへ添付 |
| A3 メトリクス整合 | `tradectl metrics report --window 1h --kind sla`にPacket変更が反映（新ラベル等）されているか | トレーダー | Markdown抜粋 |
| A4 Rollback試行 | Rollback手順を試し、元の挙動へ戻ることを確認 | 開発補佐 | 実行ログ/コマンド履歴 |
| A5 Runbook更新 | 対応するRunbook箇所が更新され、手順に差異が無いか確認 | 運用担当 | `git diff docs/runbooks`添付 |

- 受入完了後に`tradectl ops agenda --date <翌営業日>`を実行し、当日のTODOへ新手順が反映されているか確認する。反映されない場合は`docs/development_plan.md`のBacklogへ記録。
- Packetごとに`ops_worklog`へ`{"task":"packet_review","packet_id":"EP04-P1","duration_min":15}`を追記し、WIP制限の効果を分析する。
- **初期テンプレート位置と保守責任**: トレーダー受入記録は`docs/trader_signoff/TEMPLATE.md`をコピーして作成し、Trader Leadが雛形維持とエビデンス格納先の整備を担当する。Ops Managerは`docs/trader_signoff/<EPxx-Py>/`配下の資産を監査し、完了後に`docs/governance/feature_flag_register.md`と整合させる。

## 3. Codexレビューフィードバックフォーマット
```
Packet: EP04-P1
Diff summary: ticket.builder + interfaces/cli/board
Tests: pytest -k ticket_builder (pass), approvaltests (updated snapshot)
Trader notes: Spread badge OK, RiskDisclosure pending banner text request
Follow-up: Update copywriting (docs/development_plan.md#design-alignment-backlog)
```
- フィードバックはPRマージ前に`docs/development_plan.md#update-log-utc`へ追記し、改善要望は3件以内に絞り、優先度を`{must,should,nice}`でタグ付けする。

## 4. Pull Request テンプレート（Codex向け）
```
## Summary
- (必須) 何を/なぜ
- (リスク) Spread/Kill Switch/Consentへの影響
- (運用) Runbook/手動手順の変化

## Testing
- [ ] poetry run pytest -k <keyword>
- [ ] tradectl <command>
- [ ] その他

## Screenshots / Artifacts
- CLIスナップショット or レポートパス

## Rollback Plan
- スナップショット/Configロールバック手順

## Checklist
- [ ] Feature Flag初期値確認
- [ ] docs/runbooks 更新（対象: GOV-STRAT-01 / RUN-ACC-01 / RUN-AUD-02 / RUN-REC-02 / RUN-TAX-01 など必要なもの）
- [ ] Runbookエビデンス添付（`reports/governance/runbook_inventory_status.json`・`reports/audit/reconciliation/`・`reports/tax/`等へのリンク）
- [ ] KPI影響記録
- [ ] `make check-doc-sync`（Runbook/詳細設計の差分あり、またはRUN-POST-03でTODO起票済み）
```
- CodexにはPR本文を上記形式で提出させ、チェックボックスは実行済み項目のみ`[x]`にする。実行できない項目は理由をPRコメントで説明させる。

## 5. Promptパッケージ保管ルール (Legacy)
- 旧Prompt Packageは`docs/archive/prompt_packages/`に保管（参照のみ）。
- 現行のフィードバック記録は`docs/development_plan.md#update-log-utc`に集約する。

## 6. Codexレビューメモ例
```
### Review Notes (2025-02-20 / EP-01 data.service)
- 👍 Resyncログの`failover_used`がRunbookと一致。
- ✅ pytest -k data_pipeline OK (ログ添付あり)。
- ⚠️ SpreadCooldown解除文言がRunbook表現とズレ → 次回PRで共通化タスクを起票。
- 📌 KPIログ `metrics/data_ingestion_sla.jsonl` でp95=178s。目標<180sギリギリのため、M1.1で追加改善を検討。
```
- レビューメモは`docs/development_plan.md#update-log-utc`へ日付順に追記する。トレーダーはこのログをもとに運用改善メモを作成する。
