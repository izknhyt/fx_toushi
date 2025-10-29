# Config scaffolding overview

このディレクトリは詳細設計 §3.1 / §3.5 / §4.4 に基づく設定ファイルの雛形を提供します。`CONFIG-SCAFF-01`
フォローアップとして、JSON Schema（`docs/schemas/`）とRunbook/Validation Data Playbookの導線を整理し、後続PRでの実装/テスト
を容易にします。

| ファイル | 想定スキーマ | 主要参照セクション | Runbook / Validation Data Playbook | 備考 |
| --- | --- | --- | --- | --- |
| `strategy_manifest.yaml` | `docs/schemas/strategy_manifest.schema.json` | 詳細設計 §3.5, §4.4.1 | STRAT-PROMOTE-01, `reports/validation_log/AC-46_*.md` | 戦略の有効化/優先度/データ要件。`schema_version`更新時はManifest検証テストを追加。 |
| `feature_pipeline.yaml` | `docs/schemas/feature_pipeline.schema.json` | 詳細設計 §3.4〜§3.5 | STRAT-M1-VALIDATION, `reports/validation_log/AC-01_*.md`, `AC-07_*.md` | 指標ON/OFFと窓長。Guarded運用時のFlagもここで切替。 |
| `board_modes.yaml` | `docs/schemas/board_modes.schema.json` | 詳細設計 §2.5, §3.5 | RUN-DATA-05, RUN-SPREAD-03, RUN-RISK-01 | BoardMode遷移時のエスカレーションリンクを集約。`schema/gate_state.sample.json`と整合させる。 |
| `reduce_only.yaml` | `docs/schemas/human_gate_config.schema.json` | 詳細設計 §3.5.6, §5.12 | RUN-RISK-02, RUN-RISK-03 | Human GateダブルアックとReduce-Only優先度の既定値。`config/profiles/*.yaml::gates`の上書きと整合させる。 |
| `profiles/backtest.yaml` | `docs/schemas/cfg.schema.json` | 詳細設計 §3.1, §4.4 | STRAT-M1-VALIDATION | バックテスト専用の最小構成。`ModeContext`再現用。 |
| `profiles/paper.yaml` | `docs/schemas/cfg.schema.json` | 詳細設計 §3.1, §4.4 | RUN-DATA-05, RUN-HITL-01, `reports/validation_log/AC-45_*.md` | yfinance/dukascopyのSLA閾値とBoardMode既定値。 |
| `profiles/live.yaml` | `docs/schemas/cfg.schema.json` | 詳細設計 §3.1, §4.4, §6.7 | RUN-RISK-01, RUN-SPREAD-03, STRAT-PROMOTE-01 | ブローカー接続前提のプレースホルダ。Kill Switch/BoardMode制御を明示。 |
| `ops.yaml` | `docs/schemas/ops_config.schema.json` | 詳細設計 §52.2 | [RUN-DATA-05](../docs/runbooks/RUN-DATA-05.md), [RUN-RISK-01](../docs/runbooks/RUN-RISK-01.md), [`reports/validation_log/templates/weekly.md`](../reports/validation_log/templates/weekly.md) | Automation Effect Tracker の閾値/対象タスク/通知経路。週次レビューで`review_window_weeks`を見直し、Runbook記録と同期。 |
| `roles.yaml` | `docs/schemas/roles_config.schema.json` | 詳細設計 §52, §57, §68 | [STRAT-PROMOTE-01](../docs/runbooks/STRAT-PROMOTE-01.md), [GOV-AUD-01](../docs/runbooks/GOV-AUD-01.md), [`reports/validation_log/templates/playbook_entry.md`](../reports/validation_log/templates/playbook_entry.md) | CLI権限とRunbookサインオフの責任者。ロール更新時はValidationログとサイン取得を必須化。 |
| `swap_rates.csv` | ---（CSVテンプレート、`funding`系テストで検証予定） | 詳細設計 §3.12, §4.7, Runbook `RUN-FUND-01/02` | RUN-FUND-01, RUN-FUND-02, `reports/validation_log/templates/funding_daily.md` | 日次の手動更新対象。Shadow CSVとハッシュ照合する。 |
| `sla_thresholds/default.yaml`<br>`sla_thresholds/active.yaml` | `docs/schemas/sla_threshold_profile.schema.json` | 詳細設計 §3.1, §4.4, §9.4.4 | RUN-DATA-05, RUN-DATA-06, `reports/validation_log/AC-45_*.md` | データSLAターゲットの基準値と適用中値。Runbook承認ログと同期。 |
| `schema/gate_state.sample.json` | `docs/schemas/gate_state.schema.json` | 詳細設計 §4.2, §5.4 | RUN-RISK-01, RUN-SPREAD-03 | GateStateスナップショットの雛形。Reduce-OnlyやSpreadクールダウンの表示テキストと同期。 |

## スモークテスト

- `pytest -k config_schema_smoke` — JSON Schema による雛形検証。`strategy_manifest`/`feature_pipeline`/`board_modes`/`profiles/*`/`sla_thresholds/*`と`schema/gate_state.sample.json`を対象とする。
- `pytest -k strategy_manifest` / `pytest -k strategy_registry` — Manifest と Registry の読み込みテスト（詳細設計 §4.4.1 推奨）。
- `pytest -k funding` — Funding CSV読み込みとハッシュ突合（将来追加予定）を対象としたテスト。列構成を変更した場合はテスト更新を忘れずに。
- `make sla-report` — SLA プロファイルと `metrics/data_ingestion_sla.jsonl` の整合確認（RUN-DATA-05 手順3参照）。

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
