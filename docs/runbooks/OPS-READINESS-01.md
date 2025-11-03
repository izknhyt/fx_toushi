# OPS-READINESS-01: オペレーションレディネス評価手順

> **ACカバレッジ**: AC-51, AC-63  
> **Runbook版数**: v1.1  
> **最終更新日**: 2025-03-23  
> **最終更新者**: Ops Manager (Doc Maintainer)

## 目的
- バックアップ整合性、Runbook整備率、演習実施状況を定量化し、`ops_readiness_score`が閾値(`config/ops_readiness.yaml::thresholds.min_score`)を下回らないよう維持する。
- スコア低下時の是正アクションとKill Switch解除条件を明文化し、リリース／戦略昇格のGo/No-Go判断を迅速化する。
- CLI (`tradectl ops readiness`)・スキーマ検証・証跡パスの三点セットを`reports/validation_log/ops_readiness_<YYYYWW>.md`へ保存し、週次レビューと監査に備える。

> **M1 Core注記**: CLIは`OpsReadinessEvaluatorStub`（`status="not_assessed"`）を返す。評価自体は手動で実施し、CLI出力をEvidenceとして添付する。M2以降は自動スコア算出を有効化予定。

## トリガー
- 週次Opsレビュー（金曜 19:00 JST）の前後、または`Scheduler(job=ops_readiness_weekly)`完了後。
- `HealthMonitor`が`ops_readiness_low`で`soft_stop`を発火したとき。
- リリース／戦略昇格／DR演習前の事前チェック、または監査リクエスト受領時。

## 手順
1. **証跡取得 (`collect`)**
   - `tradectl ops readiness --explain --output json`を実行し、出力を`reports/governance/ops_readiness_<YYYYWW>.json`として保存する。M1では次のようなスタブ応答を記録する。

     ```console
     $ tradectl ops readiness --explain --output json
     {
       "status": "not_assessed",
       "score": null,
       "components": [],
       "notes": "M1 Core placeholder. Refer to docs/runbooks/OPS-READINESS-01.md#score-evaluation."
     }
     ```
   - `config/ops_readiness.yaml`の`evidence_paths`に列挙された各ファイル（例: `reports/drill/backup_integrity.md`, `reports/ops/degradation_log/<date>.md`, `docs/runbooks/`更新ログ）が最新であるか確認する。
   - 証跡リストとCLIログは`reports/validation_log/ops_readiness_<YYYYWW>.md`の`Collection`節へ貼り付ける。
2. **スキーマ/テンプレ検証 (`validate`)**
   - `poetry run schema-validate config/ops_readiness.yaml --schema docs/schemas/ops_readiness.schema.json`
   - `poetry run schema-validate config --schema docs/schemas/config_bundle.schema.json`
   - `pytest -k ops_readiness`（テスト未実装の場合は`CONFIG-SCAFF-01`で追加する）。ログはEvidenceに追記する。
   - `make check-ops-readiness`（`tools/check_ops_readiness.py`）を実行し、Evidenceパスの存在と更新時刻を検証する。エラーが出た場合は`OpsEvidenceMissing`イベントを`logs/health/events.jsonl`で確認し、本Runbookの`#evidence-recovery`節へ移行する。
3. **スコア評価 (`score-evaluation`)**
   - バックアップ: `reports/drill/backup_integrity.md`を確認し、直近実施日とハッシュ照合結果を記録。欠損がある場合はDRチームへ再実行を依頼する。
   - Runbook整備: `docs/runbooks/`の更新履歴（`git log --since "last friday"`）を確認し、レビュー未完了のRunbookがある場合は担当を割り当てる。
   - 演習ログ: `reports/drill/emergency/<scenario>.md`および`reports/drill/ops_incident_*.md`を突合し、未完了タスクは`tickets/ops_followup/<date>.md`でトラッキングする。
   - それぞれのサブスコアと改善タスクを`reports/validation_log/ops_readiness_<YYYYWW>.md`の`Score Sheet`へ記録し、合計スコアを算出する（M1では手計算）。
4. **是正アクション (`remediation`)**
   - スコアが`config/ops_readiness.yaml::thresholds.min_score`未満の場合は以下を実施。
     1. Ops Managerが`tradectl board --guarded --reason ops_readiness_low`を実行し、Reduce-Only状態へ移行。
     2. `RUN-RISK-07`と連携し、Kill Switchレビュー（`tradectl kill-switch review --reason ops_readiness --strategy <id>`）を起票。
     3. 不足証跡の回復タスクを`docs/runbooks/daily_agenda/<date>.md`へ追加。完了したら`make check-ops-readiness`を再実行する。
5. **サインオフとアーカイブ (`sign-off`)**
   - Ops Manager / Quant Lead / Product Ownerが`reports/validation_log/ops_readiness_<YYYYWW>.md`へイニシャルを記入し、`docs/review_log.md`の`OPS-{{report_week}}`エントリと相互リンクする。
   - `tradectl status --json`で`ops_readiness`関連バナーが解除されたことを確認し、`health.ack --reason ops_readiness_recovered`を実行してIDをEvidenceに記録する。
   - 週次レポート (`reports/weekly/<YYYY-WW>.md`) の`Ops Evidence Checklist`節を更新し、本Runbookで取得した証跡パスを貼り付ける。

## 証跡と保存先
- `reports/governance/ops_readiness_<YYYYWW>.{json,md}`
- `reports/validation_log/ops_readiness_<YYYYWW>.md`
- `metrics/ops_readiness.jsonl`（将来実装予定。現状は手動でエントリ追加）
- `logs/health/events.jsonl`（`ops_readiness_low`, `ops_readiness_recovered`）
- `docs/review_log.md`（カテゴリ: `OPS-<YYYYWW>`）

## エスカレーション (`#evidence-recovery`)
- `make check-ops-readiness`が失敗した場合は、欠損ファイルを`CONFIG-SCAFF-01`の手順に沿って再生成する。
- バックアップ証跡が未更新の場合は`RUN-DATA-06`（Catch-up手順）と連携し、DRチームへ再実施を依頼する。
- 演習ログ欠損は`RUN-OPS-AGENDA-01`でOpsアジェンダに追加し、完了後に再評価を実施する。

## 責任者
- **一次担当**: Ops Manager（評価実施・証跡回収）
- **レビュー**: Product Owner（Kill Switch判断）、Risk Manager（Reduce-Only解除判断）
- **サポート**: インフラ担当（バックアップ整合）、Quant Lead（Runbook整備率評価）
