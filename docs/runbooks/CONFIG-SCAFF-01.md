# CONFIG-SCAFF-01: Config雛形整備ハンドオフ手順

> **ACカバレッジ**: AC-45, AC-51, AC-63  
> **Runbook版数**: v1.0  
> **最終更新日**: 2025-03-23  
> **最終更新者**: Ops Manager (Doc Maintainer)

## 目的
- `config/`配下の雛形を最新スキーマと整合させ、Codex/Jr.SEが即座に`pytest -k config_schema_smoke`を実行できる状態を維持する。
- `CONFIG-SCAFF-01` Packetで要求される CLI / テスト / 証跡パスを標準化し、レビュー時に差分と検証ログをワンセットで提示する。
- Runbook更新とConfigスキーマ変更の相互依存を明示し、設定ドリフトによるAcceptable Degradation発火を未然に防ぐ。

## トリガー
- 新規環境の立ち上げ、または`tools/scripts/config_init.py`更新後に雛形を再配布するとき。
- `docs/schemas/*.json`（特に`config_bundle.schema.json`）へ破壊的変更を加えたとき。
- Ops/Quantレビューで雛形欠落・証跡不備が判明したとき（例: `RUN-DATA-05`/`RUN-RISK-07`が参照する閾値が未登録）。

## 手順
1. **事前確認**
   - `git status --short`でワークツリーがクリーンであることを確認。既存差分がある場合は別ブランチへ退避する。
   - 変更対象とするスキーマ/設定ファイルを`docs/schemas/CHANGELOG.md`と`config/README.md`で再確認し、このRunbookの最新版に沿っているかチェックする。
2. **雛形プレビュー (`dry-run`)**
   - `make config-init --dry-run`を実行し、生成/上書き対象を確認する。出力は`reports/validation_log/config_init_<date>.md`の`Dry Run`節へ貼り付ける。

     ```console
     $ make config-init --dry-run
         -> would write config/risk_policy.yaml
         -> would write config/scoreboard.yaml
         -> would update config/sla_thresholds/default.yaml
     ```
   - `dry-run`で変更予定が無いにも関わらず設計差分が残る場合は、`tools/scripts/config_init.py`のテンプレ更新を優先する。
3. **雛形展開**
   - `make config-init`を実行し、`config/*.yaml`や`config/sla_thresholds/*.yaml`が最新テンプレへ置き換わったことを確認する。
   - 生成ログを`reports/validation_log/config_init_<date>.md`の`Generation Log`節に保存し、`git diff config/`で差分を確認する。
4. **スキーマ検証**
   - `poetry run schema-validate config --schema docs/schemas/config_bundle.schema.json`を実行し、成功ログをRunbook証跡と同じMarkdownに添付する。
   - 個別検証が必要な場合は以下も実行する。
     - `poetry run schema-validate config/risk_live_guard.yaml --schema docs/schemas/risk_live_guard.schema.json`
     - `poetry run schema-validate config/ops_readiness.yaml --schema docs/schemas/ops_readiness.schema.json`
5. **Pytestスモーク**
   - `pytest -k config_schema_smoke`および`pytest -k schema_validate_bundle`を順に実行し、Exit code 0を確認。両方のログを`reports/validation_log/config_init_<date>.md`へ追記する。
   - CIに組み込む場合は`ci/templates/python_smoke.yml`で同じコマンドを使用する。
6. **ドキュメント/Runbook整合**
   - `config/README.md`の該当セクション（例: `Live Guard`, `Ops Readiness`）を更新し、Runbookリンクと管理責任者が最新であることを確認する。
   - Runbook参照が増えた場合は`docs/runbooks/*`の該当手順へハイパーリンクを追加する。
   - 変更内容を`docs/review_log.md`へ記録（カテゴリ: `CONFIG-SCAFF-01`、週次Opsレビューで確認）。
7. **証跡パッケージ**
   - `reports/validation_log/config_init_<date>.md`を完成させ、以下のファイルをリンクする。
     - `reports/weekly/evidence/<YYYY-WW>/config_bundle_diff.md`（任意: 週次確認用 diff）
     - `metrics/schema_validate.jsonl`（`schema-validate` CLIの履歴）
     - `logs/ops/workload.log`（Ops作業時間メトリクスが必要な場合）
   - PRでは上記Markdownと主要コマンドのログを添付し、`CONFIG-SCAFF-01`チェックリストを満たしたことを明示する。

8. **自動化ショートカット**
   - `make config-evidence`を実行すると本手順2〜5（`config_init` / `schema-validate` / `pytest -k config_schema_smoke`）のログを収集し、`reports/validation_log/config_init_<date>.md`を自動生成する。
   - 運用レビュー時は`make verify-config-evidence ARGS="--grace-days 2"`（必要に応じ調整）を実行し、直近のEvidenceファイルが存在するか確認する。欠損している場合は`RUN-POST-03`の欠損フローに従ってIssueを起票する。

## 補足
- `tools/scripts/config_init.py`へ新規テンプレートを追加した際は、対応する`docs/schemas/*.json`と`tests/`のスモークケースを同じPRで更新する。
- 既存設定との差分が大きい場合は`make config-init --overwrite-existing=false`で安全に確認し、必要なファイルのみ手動反映する。
- `config/ops_readiness.yaml`や`config/risk_live_guard.yaml`の`runbook_ref`はスキーマで`RUN-RISK-07`等の形式制約があるため、更新後は`git grep "RUN-RISK-07"`でハードコード漏れがないか確認する。

## 責任者
- **一次担当**: Ops Manager（雛形整備とEvidence作成）
- **レビュー**: Quant Lead（スキーマ整合性）、Product Owner（Runbook整合）
- **エスカレーション先**: RUN-RISK-07（リスク閾値変更が伴う場合）、GOV-STRAT-01（戦略マニフェスト更新時）
