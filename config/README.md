# Config scaffolding overview

このディレクトリは詳細設計 §3.1 / §3.5 / §4.4 に基づく設定ファイルの雛形を提供します。`CONFIG-SCAFF-01`
フォローアップとして、JSON Schema（`docs/schemas/`）とRunbook/Validation Data Playbookの導線を整理し、後続PRでの実装/テスト
を容易にします。

| ファイル | 想定スキーマ | 主要参照セクション | Runbook / Validation Data Playbook | 備考 |
| --- | --- | --- | --- | --- |
| `strategy_manifest.yaml` | `docs/schemas/strategy_manifest.schema.json` | 詳細設計 §3.5, §4.4.1 | STRAT-PROMOTE-01, `reports/validation_log/AC-46_*.md` | 戦略の有効化/優先度/データ要件。`schema_version`更新時はManifest検証テストを追加。 |
| `feature_pipeline.yaml` | `docs/schemas/feature_pipeline.schema.json` | 詳細設計 §3.4〜§3.5 | STRAT-M1-VALIDATION, `reports/validation_log/AC-01_*.md`, `AC-07_*.md` | 指標ON/OFFと窓長。Guarded運用時のFlagもここで切替。 |
| `board_modes.yaml` | `docs/schemas/board_modes.schema.json` | 詳細設計 §2.5, §3.5 | RUN-DATA-05, RUN-SPREAD-03, RUN-RISK-01 | BoardMode遷移時のエスカレーションリンクを集約。 |
| `profiles/backtest.yaml` | `docs/schemas/cfg.schema.json` | 詳細設計 §3.1, §4.4 | STRAT-M1-VALIDATION | バックテスト専用の最小構成。`ModeContext`再現用。 |
| `profiles/paper.yaml` | `docs/schemas/cfg.schema.json` | 詳細設計 §3.1, §4.4 | RUN-DATA-05, RUN-HITL-01, `reports/validation_log/AC-45_*.md` | yfinance/dukascopyのSLA閾値とBoardMode既定値。 |
| `profiles/live.yaml` | `docs/schemas/cfg.schema.json` | 詳細設計 §3.1, §4.4, §6.7 | RUN-RISK-01, RUN-SPREAD-03, STRAT-PROMOTE-01 | ブローカー接続前提のプレースホルダ。Kill Switch/BoardMode制御を明示。 |
| `sla_thresholds/default.yaml`<br>`sla_thresholds/active.yaml` | `docs/schemas/sla_threshold_profile.schema.json` | 詳細設計 §3.1, §4.4, §9.4.4 | RUN-DATA-05, RUN-DATA-06, `reports/validation_log/AC-45_*.md` | データSLAターゲットの基準値と適用中値。Runbook承認ログと同期。 |

## スモークテスト

- `pytest -k config_schema_smoke` — JSON Schema による雛形検証（今後実装予定）。
- `pytest -k strategy_manifest` / `pytest -k strategy_registry` — Manifest と Registry の読み込みテスト（詳細設計 §4.4.1 推奨）。
- `make sla-report` — SLA プロファイルと `metrics/data_ingestion_sla.jsonl` の整合確認（RUN-DATA-05 手順3参照）。

## 運用メモ

1. `schema_version` を更新する際は必ず `docs/schemas/CHANGELOG.md` に追記し、Runbook履歴 (`reports/governance/runbook_changelog.md`)
   へリンクを記録してください。
2. Validation Data Playbook（要件定義 §8.2）の AC-01 / AC-07 / AC-45 行に、該当ファイルのコミットハッシュと承認者サインを記録します。
3. `tradectl config diff --profile <name>` コマンド実装時の初期データとして本雛形を利用し、差分レビューで Runbook とスキーマの整合を
   確認します。
