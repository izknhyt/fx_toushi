# Config scaffolding overview

このディレクトリは詳細設計 §3.1 / §3.5 / §4.4 に基づく設定ファイルの雛形を提供します。`CONFIG-SCAFF-01`
フォローアップとして、JSON Schema（`docs/schemas/`）とRunbook/Validation Data Playbookの導線を整理し、後続PRでの実装/テスト
を容易にします。

| ファイル | 想定スキーマ | 主要参照セクション | Runbook / Validation Data Playbook | 備考 |
| --- | --- | --- | --- | --- |
| `strategy_manifest.yaml` | `docs/schemas/strategy_manifest.schema.json` | 詳細設計 §3.5, §4.4.1 | STRAT-PROMOTE-01, `reports/validation_log/AC-46_*.md` | 戦略の有効化/優先度/データ要件。`schema_version`更新時はManifest検証テストを追加。 |
| `feature_pipeline.yaml` | `docs/schemas/feature_pipeline.schema.json` | 詳細設計 §3.4〜§3.5 | STRAT-M1-VALIDATION, `reports/validation_log/AC-01_*.md`, `AC-07_*.md` | 指標ON/OFFと窓長。Guarded運用時のFlagもここで切替。 |
| `feature_flags.yaml` | `docs/schemas/feature_flags.schema.json` | 詳細設計 §0.6.13, §8.6 | RUN-FEATURE-FLAG-01, RUN-RISK-01, RUN-SPREAD-03 | Backtest/Paper/Live のFlag既定値とガバナンス情報を単一管理。Runbook証跡とテレメトリ前提を明記する。 |
| `board_modes.yaml` | `docs/schemas/board_modes.schema.json` | 詳細設計 §2.5, §3.5 | RUN-DATA-05, RUN-SPREAD-03, RUN-RISK-01 | BoardMode遷移時のエスカレーションリンクを集約。`schema/gate_state.sample.json`と整合させる。 |
| `execution_model.yaml` | `docs/schemas/execution_model.schema.json` | 詳細設計 §3.6, §4.4 | [RUN-HITL-01](../docs/runbooks/RUN-HITL-01.md), [RUN-RISK-01](../docs/runbooks/RUN-RISK-01.md), [`reports/validation_log/templates/weekly.md`](../reports/validation_log/templates/weekly.md) | ヒューマン遅延・スリッページ分布とエントリーモード閾値のベースライン。シンボル/レジーム別上書きを記録し、Runbook承認ログと紐付ける。 |
| `scoring.yaml` | `docs/schemas/scoring_config.schema.json` | 詳細設計 §3.7, §4.4.4 | RUN-SCORE-01, `reports/diagnostics/scoring_<date>.md` | スコア係数・PF乖離ガード・診断閾値。`tradectl scoring diagnostics`と共有。 |
| `scoreboard.yaml` | `docs/schemas/scoreboard.schema.json` | 付録G.1, §4.4.5 | RUN-GOV-BOARD-01, RUN-RISK-07 | Strategy Scoreboard のα/Decay閾値とウォッチリスト判定条件。 |
| `alpha_profiles.yaml` | `docs/schemas/alpha_profiles.schema.json` | 詳細設計 §88, §4.4.7 | RUN-ALPHA-PROFILE-01, RUN-ALPHA-FEEDBACK-01 | Hands-off/動的サイジング用プロファイルと`max_dynamic_adjust_pct`上限。 |
| `risk_live_guard.yaml` | `docs/schemas/risk_live_guard.schema.json` | 詳細設計 §3.8, §4.4.3 | RUN-RISK-07 | ライブ性能ガードのPF/Sharpe/Latency基準と通知ルール。 |
| `ops_readiness.yaml` | `docs/schemas/ops_readiness.schema.json` | 詳細設計 §3.27, §4.4.6 | OPS-READINESS-01, RUN-RISK-07 | Ops レビュー重みと証跡パス。`make check-ops-readiness` の入力。 |
| `reduce_only.yaml` | `docs/schemas/human_gate_config.schema.json` | 詳細設計 §3.5.6, §5.12 | RUN-RISK-02, RUN-RISK-03 | Human GateダブルアックとReduce-Only優先度の既定値。`config/profiles/*.yaml::gates`の上書きと整合させる。 |
| `profiles/backtest.yaml` | `docs/schemas/cfg.schema.json` | 詳細設計 §3.1, §4.4 | STRAT-M1-VALIDATION | バックテスト専用の最小構成。`ModeContext`再現用。 |
| `profiles/paper.yaml` | `docs/schemas/cfg.schema.json` | 詳細設計 §3.1, §4.4 | RUN-DATA-05, RUN-HITL-01, `reports/validation_log/AC-45_*.md` | yfinance/dukascopyのSLA閾値とBoardMode既定値。 |
| `profiles/live.yaml` | `docs/schemas/cfg.schema.json` | 詳細設計 §3.1, §4.4, §6.7 | RUN-RISK-01, RUN-SPREAD-03, STRAT-PROMOTE-01 | ブローカー接続前提のプレースホルダ。Kill Switch/BoardMode制御を明示。 |
| `ops.yaml` | `docs/schemas/ops_config.schema.json` | 詳細設計 §52.2 | [RUN-DATA-05](../docs/runbooks/RUN-DATA-05.md), [RUN-RISK-01](../docs/runbooks/RUN-RISK-01.md), [`reports/validation_log/templates/weekly.md`](../reports/validation_log/templates/weekly.md) | Automation Effect Tracker の閾値/対象タスク/通知経路。週次レビューで`review_window_weeks`を見直し、Runbook記録と同期。 |
| `ops/drill_scenarios.yaml` | ---（詳細設計 §53, 基本設計 §202 を参照） | 詳細設計 §53, 基本設計 §202 | [RUN-OPS-AGENDA-01](../docs/runbooks/RUN-OPS-AGENDA-01.md), [RUN-DATA-05](../docs/runbooks/RUN-DATA-05.md), [`docs/validation_playbook/index.md`](../docs/validation_playbook/index.md) | Ops Drill シナリオ登録カタログ。RunbookトレーサビリティとValidation Playbook（AC-40/AC-45）証跡を同期する。 |
| `roles.yaml` | `docs/schemas/roles_config.schema.json` | 詳細設計 §52, §57, §68 | [STRAT-PROMOTE-01](../docs/runbooks/STRAT-PROMOTE-01.md), [GOV-AUD-01](../docs/runbooks/GOV-AUD-01.md), [`docs/validation_playbook/dataset_template.md`](../docs/validation_playbook/dataset_template.md) | CLI権限とRunbookサインオフの責任者。ロール更新時はValidationログとサイン取得を必須化。 |
| `swap_rates.csv` | ---（CSVテンプレート、`funding`系テストで検証予定） | 詳細設計 §3.12, §4.7, Runbook `RUN-FUND-01/02` | RUN-FUND-01, RUN-FUND-02, `reports/validation_log/templates/funding_daily.md` | 日次の手動更新対象。Shadow CSVとハッシュ照合する。 |
| `sla_thresholds/default.yaml`<br>`sla_thresholds/active.yaml` | `docs/schemas/sla_threshold_profile.schema.json` | 詳細設計 §3.1, §4.4, §9.4.4 | RUN-DATA-05, RUN-DATA-06, `reports/validation_log/AC-45_*.md` | データSLAターゲットの基準値と適用中値。Runbook承認ログと同期。 |
| `schema/gate_state.sample.json` | `docs/schemas/gate_state.schema.json` | 詳細設計 §4.2, §5.4 | RUN-RISK-01, RUN-SPREAD-03 | GateStateスナップショットの雛形。Reduce-OnlyやSpreadクールダウンの表示テキストと同期。 |

## スモークテスト

- `pytest -k config_schema_smoke` — JSON Schema による雛形検証。`strategy_manifest`/`feature_pipeline`/`board_modes`/`execution_model`/`ops`/`roles`/`broker_rules`/`profiles/*`/`sla_thresholds/*`に加え、本稿で追加した`scoring`/`scoreboard`/`risk_live_guard`/`ops_readiness`/`feature_flags`を対象とする。
- `pytest -k feature_flags` — `config/feature_flags.yaml` の既定値とRunbook参照・危険度分類を検証するガバナンステスト。Runbook `RUN-FEATURE-FLAG-01` とテレメトリ整合性を継続確認する。
- `poetry run schema-validate config --schema docs/schemas/config_bundle.schema.json` — `config/`全体の必須ファイルが揃い、個別スキーマと整合していることを確認。
- `poetry run schema-validate config/scoring.yaml --schema docs/schemas/scoring_config.schema.json`（`risk_live_guard.yaml`/`scoreboard.yaml`/`ops_readiness.yaml`も同様） — ランブック準拠のスキーマ検証をCLIと同一条件で実行。
- `make sla-report` — SLA プロファイルと `metrics/data_ingestion_sla.jsonl` の整合確認（RUN-DATA-05 手順3参照）。

## 初期化コマンド

- `make config-init` — `tools/scripts/config_init.py` を呼び出し、欠落している設定ファイルを生成する。差分のみを確認したい場合は `make config-init ARGS=--dry-run` を使用。
- 初期化後は本節の `schema-validate` コマンドと `pytest -k config_schema_smoke` を実行し、結果ログを `artifacts/` もしくは `reports/validation_log/` に保存してPRへ添付する。

## 運用メモ

1. `schema_version` を更新する際は必ず `docs/schemas/CHANGELOG.md` に追記し、Runbook履歴 (`reports/governance/runbook_changelog.md`)
   へリンクを記録してください。
2. Validation Data Playbook（要件定義 §8.2）の AC-01 / AC-07 / AC-45 行に、該当ファイルのコミットハッシュと承認者サインを記録します。
3. `tradectl config diff --profile <name>` コマンド実装時の初期データとして本雛形を利用し、差分レビューで Runbook とスキーマの整合を
   確認します。

### Ops / Roles 設定のメンテナンス

- **`config/ops.yaml`** — Automation Effect Tracker の閾値や許可タスクは、週次Opsレビュー（[RUN-DATA-05](../docs/runbooks/RUN-DATA-05.md)）
  とリスク報告（[RUN-RISK-01](../docs/runbooks/RUN-RISK-01.md)）のサインオフ後に更新します。`notify_channels`を変更した場合は
  Validationログテンプレート（[`reports/validation_log/templates/weekly.md`](../reports/validation_log/templates/weekly.md)）で
  通知証跡セクションを追記し、Automation EffectハイライトがRunbookに反映されているか確認してください。
- **`config/roles.yaml`** — ロール追加/削除時は Strategy Board ガバナンス手順（[STRAT-PROMOTE-01](../docs/runbooks/STRAT-PROMOTE-01.md)）
  と監査手順（[GOV-AUD-01](../docs/runbooks/GOV-AUD-01.md)）を参照し、Validation Data Playbook エントリ（[`reports/validation_log/templates/playbook_entry.md`](../reports/validation_log/templates/playbook_entry.md)）に
  署名と根拠リンクを残します。`members[*].principal_id` を更新したら Access Registry 側の `register_principal` ワークフローが同期されているか
  を確認し、変更理由を`notes`に記録してください。

### Ops Drill シナリオ構成のレビュー手順

1. `config/ops/drill_scenarios.yaml` を更新する前に、ドリル計画/容量の調整手順（[RUN-OPS-AGENDA-01](../docs/runbooks/RUN-OPS-AGENDA-01.md)）
   と週次Opsレビューの手順（[RUN-DATA-05](../docs/runbooks/RUN-DATA-05.md)）を確認し、Runbook記載のトリガー条件・承認者がシナリオ定義に反映されているかをチェックします。
2. ドリルのRunbookリンクやValidation Playbook IDを追加/変更した場合は、Validation Data Playbookの該当行（AC-40/AC-45など）を
  [`docs/validation_playbook/index.md`](../docs/validation_playbook/index.md) とテンプレート群に基づいて更新し、`maintained_by`/`last_reviewed_at`を最新化してください。
3. 設計整合性を保つため、詳細設計 §53（Ops Drill Orchestrator）および基本設計 §202 に記載されたフィールド要件と照合し、シナリオ毎に
   `trigger`・`expected_duration_min`・`impact_tags`の根拠をドリルレポート（[`docs/templates/drill_report.md`](../docs/templates/drill_report.md)）と突合します。

## `swap_rates.csv` 手動更新ガイド

FundingService は `config/swap_rates.csv` を日次で読み込み、`reports/funding/swap_rates_shadow.csv` とハッシュ照合します。Ops/Risk/POが Runbook `RUN-FUND-01` に沿って手動更新する際は以下の列ルールを守ってください。

| 列名 | 説明 | 例 | 必須 |
| --- | --- | --- | --- |
| `pair` | 通貨ペア（ブローカー表記に準拠）。`EURUSD` など 6 文字固定を推奨。 | `EURUSD` | ✅ |
| `base_currency` | ベース通貨 ISO コード。 | `EUR` | ✅ |
| `quote_currency` | クォート通貨 ISO コード。 | `USD` | ✅ |
| `swap_long` | ロング（買い）保有時に日次で受払うスワップポイント。負値は支払い。 | `-5.10` | ✅ |
| `swap_short` | ショート（売り）保有時に日次で受払うスワップポイント。 | `1.80` | ✅ |
| `triple_day` | 三倍日が適用される曜日（`Mon`〜`Sun`）。ブローカー規定に合わせる。 | `Wed` | ✅ |
| `rollover_time_utc` | ロールオーバー基準時刻（UTC表記、`HH:MM`）。 | `21:00` | ✅ |
| `last_verified_at` | レートを確認した日時（ISO 8601, UTC）。Runbook記録と一致させる。 | `2025-03-01T06:00:00Z` | ✅ |
| `data_source` | 参照元やメモ。公開CSV/ブローカー名/担当者などを記載。 | `dukascopy manual input` | ✅ |

- リポジトリ初期値はプレースホルダのため、運用前に必ずブローカー提供値へ差し替えてください。
- 列の追加/削除を行う場合は `pytest -k funding` を更新し、Runbookおよび `reports/funding/daily_hash_log.md` の記載ルールも追従させてください。
- Shadow CSV（`reports/funding/swap_rates_shadow.csv`）も同じ列順を維持し、`tradectl funding sync --shadow ...` で突合します。
- ハッシュと署名の記録は `reports/funding/daily_hash_log.md` で日次一覧化し、詳細は `reports/validation_log/templates/funding_daily.md` のテンプレートへ転記します。
