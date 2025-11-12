# テストガイドライン（M1）

詳細設計書 v1.29 に記載された M1 コアの `pytest -k` 実行要件を集約し、Apple Silicon (M1) 環境で必須となる検証コマンドを以下の表に整理する。設計書上で未実装のテストは今後の Packet 作業でカバーする。

## M1 必須 `pytest -k` 一覧

| テスト名 | 目的 | pytest コマンド | 実装状況 | オーナー/メモ |
| --- | --- | --- | --- | --- |
| config_schema_smoke | `config/` 雛形を JSON Schema と突き合わせるスモーク検証。 | `pytest -k "config_schema_smoke"` | Packet `PKG-CONFIG-SCHEMA-01`でxfail雛形を登録（Schema突合実装待ち）。 | Ops Manager — `docs/implementation_packets/20250315_config_schema_smoke.md` |
| data_status_cli | レート制限ステージ評価ログを自動点検し、Ops 手順と同期する。 | `pytest -k "data_status_cli"` | CLI実装済み（stage_evalを`metrics/rate_limit_window.jsonl`へ記録）。 | Ops Manager — `metrics/rate_limit_window.jsonl`参照 |
| strategy_determinism | Backtest / Paper / Live でシグナル決定論を担保する。 | `pytest -k "strategy_determinism"` | Packet `PKG-STRAT-DETERMINISM-01`でxfail雛形を登録（決定論ハーネス実装待ち）。 | Quant Lead — `reports/implementation/20250315_pkg-strat-determinism-01/` |
| strategy_plugin_contract | Strategy Plugin Protocol への準拠を静的に検証する。 | `pytest -k "strategy_plugin_contract"` | Packet `PKG-STRAT-IFACE-01`で要件定義済（テストコード着手前）。 | Quant Lead — `docs/implementation_packets/20250312_strat_plugin_contract.md` |
| feature_context_contract | FeatureContext / FeatureFrameView の契約と `metadata.required_features` キー表との一致を検証する。 | `pytest -k "feature_context_contract and smoke"` | Packet `PKG-FEATURE-CONTEXT-01`でスモーク整備済（FeatureContext 実装待ち）。 | Quant Lead — `reports/implementation/20250315_pkg-feature-context-01/` |
| strategy_manifest | `strategy_manifest.yaml` のバリデーションとガバナンス手順の検証。 | `pytest -k "strategy_manifest"` | Packet `PKG-STRAT-MANIFEST-01`でxfail雛形を登録（Validator実装待ち）。 | Product Owner — manifest審査と連動 |
| strategy_registry | Strategy Registry のロードと Fail-Fast 振る舞いを検証する。 | `pytest -k "strategy_registry"` | Determinismハッシュ＋`strategy.determinism`ログ実装済（PKG-STRAT-REGISTRY-01エビデンス参照）。 | Quant Lead — registry seed表 |
| ticket_builder | チケット JSON 整形と HITL UX の要件を検証する。 | `pytest -k "ticket_builder"` | Packet `PKG-TICKET-BUILDER-01`でxfail雛形を登録（Checklist検証実装待ち）。 | Ops Manager — GateStateチェック |
| json_schema_validation | 取引状態およびアカウント関連 JSON Schema の整合性を検証する。 | `pytest -k "json_schema_validation"` | Packet `PKG-JSON-SCHEMA-01`で維持管理中（既存テスト活用）。 | Ops Manager — schema更新時必須 |

> **共有スプレッドシートについて**: 現在リポジトリ内に指定されたトラッキングスプレッドシートは存在しないため、本表を Ops／Codex 共通の参照元とする。

> **CLI実装状況メモ**: `tradectl data ...` サブコマンド群はまだTyperアプリへバインドされていないため、`poetry run python -m tradectl data status`は実行できません。PKG-DATA-STATUS-01でエントリを追加してからテストを解禁してください。
