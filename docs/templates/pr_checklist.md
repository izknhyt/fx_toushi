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
- **新規CLI**: `tradectl execution recalibrate` / `tradectl scoring diagnostics` / `tradectl kill-switch review`を利用するPacketは、サンプル実行ログと生成物パス（`config/execution_model.calib.yaml`, `reports/diagnostics/scoring_<date>.md`, `reports/audit/kill_switch_review/<ts>.md`）を添付し、Runbook更新との整合を明記する。
- **テンプレ同期**: ReporterやValidationテンプレを変更した場合は`reports/weekly/templates/m1_core.md`・`docs/validation_log/templates/weekly.md`・`docs/trader_signoff/TEMPLATE.md`の差分をPacketに含め、`pytest -k weekly_report_template`・`pytest -k validation_log_template`ログを添付する。
- **初期テンプレート位置と保守責任**: Implementation Packetの詳細は`docs/implementation_packets/TEMPLATE.md`をベースに作成し、Ops Managerが構造保守、Codex Liaisonが各Packetの更新履歴を追記する。関連するプロンプト差分は`docs/prompt_packages/TEMPLATE.md`を参照し、同担当者が同期する。

## 2. トレーダー受入試験テンプレ
| チェック項目 | 詳細 | 実施者 | 証跡 |
| --- | --- | --- | --- |
| A1 CLIレンダリング | `tradectl board --guarded`表示をスクリーンショット化し、RiskDisclosureバナー/Spreadバッジを確認 | トレーダー | `docs/trader_signoff/EP04-P1.md`に画像貼付 |
| A2 Ops Worklog | 新コマンド実行後に`ops_worklog.jsonl`へ記録されているか確認 | 運用担当 | JSON抜粋をテンプレへ添付 |
| A3 メトリクス整合 | `tradectl metrics report --window 1h --kind sla`にPacket変更が反映（新ラベル等）されているか | トレーダー | Markdown抜粋 |
| A4 Rollback試行 | Rollback手順を試し、元の挙動へ戻ることを確認 | 開発補佐 | 実行ログ/コマンド履歴 |
| A5 Runbook更新 | 対応するRunbook箇所が更新され、手順に差異が無いか確認 | 運用担当 | `git diff docs/runbooks`添付 |

- 受入完了後に`tradectl ops agenda --date <翌営業日>`を実行し、当日のTODOへ新手順が反映されているか確認する。反映されない場合は`docs/prompt_packages/`の改善事項へ記録。
- Packetごとに`ops_worklog`へ`{"task":"packet_review","packet_id":"EP04-P1","duration_min":15}`を追記し、WIP制限の効果を分析する。
- **初期テンプレート位置と保守責任**: トレーダー受入記録は`docs/trader_signoff/TEMPLATE.md`をコピーして作成し、Trader Leadが雛形維持とエビデンス格納先の整備を担当する。Ops Managerは`docs/trader_signoff/<EPxx-Py>/`配下の資産を監査し、完了後に`docs/governance/feature_flag_register.md`と整合させる。

## 3. Codexレビューフィードバックフォーマット
```
Packet: EP04-P1
Diff summary: ticket.builder + interfaces/cli/board
Tests: pytest -k ticket_builder (pass), approvaltests (updated snapshot)
Trader notes: Spread badge OK, RiskDisclosure pending banner text request
Follow-up: Update copywriting (docs/implementation_packets/20250222_ep04_p1.md#todo)
```
- フィードバックはPRマージ前に`docs/prompt_packages/`へ追記し、次Packetのプロンプトに引用。Codexへは改善要望を3件以内に絞り、優先度を`{must,should,nice}`でタグ付けする。

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
- [ ] docs/runbooks 更新
- [ ] KPI影響記録
```
- CodexにはPR本文を上記形式で提出させ、チェックボックスは実行済み項目のみ`[x]`にする。実行できない項目は理由をPRコメントで説明させる。

## 5. Promptパッケージ保管ルール
- `docs/prompt_packages/<YYYYMMDD>_<feature>.md`の冒頭に以下メタデータを記載:
  - `feature_id`, `epic`, `status(draft|sent|accepted|rejected)`, `codex_version` (任意)、`reviewers`
  - `related_kpi`, `runbook_refs`, `data_manifest_refs`
- 本文末尾に`## Review Feedback`セクションを必須とし、差戻し理由/改善点/次回の留意事項を箇条書き。Codexからのフィードバックも同じファイルに追記し、学習サイクルを短縮。
- 旧バージョンを再利用する場合は`---`区切り線で過去ログを残し、変更点は`diff`形式で明示する。

## 6. Codexレビューメモ例
```
### Review Notes (2025-02-20 / EP-01 data.service)
- 👍 Resyncログの`failover_used`がRunbookと一致。
- ✅ pytest -k data_pipeline OK (ログ添付あり)。
- ⚠️ SpreadCooldown解除文言がRunbook表現とズレ → 次回PRで共通化タスクを起票。
- 📌 KPIログ `metrics/data_ingestion_sla.jsonl` でp95=178s。目標<180sギリギリのため、M1.1で追加改善を検討。
```
- レビューメモは`docs/review_log.md`へ日付順に追記する。トレーダーはこのログをもとに運用改善メモを作成する。
