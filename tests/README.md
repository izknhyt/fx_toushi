# テストガイドライン（M1）

詳細設計書 v1.29 に記載された M1 コアの `pytest -k` 実行要件を集約し、Apple Silicon (M1) 環境で必須となる検証コマンドを以下の表に整理する。設計書上で未実装のテストは今後の Packet 作業でカバーする。

## M1 必須 `pytest -k` 一覧

| テスト名 | 目的 | pytest コマンド | 実装状況 |
| --- | --- | --- | --- |
| config_schema_smoke | `config/` 雛形を JSON Schema と突き合わせるスモーク検証。 | `pytest -k "config_schema_smoke"` | 未実装（テスト雛形と config スキーマの整備が未着手）。 |
| data_status_cli | レート制限ステージ評価ログを自動点検し、Ops 手順と同期する。 | `pytest -k "data_status_cli"` | 未実装（CLI／メトリクス連携のコードが未着手）。 |
| strategy_determinism | Backtest / Paper / Live でシグナル決定論を担保する。 | `pytest -k "strategy_determinism"` | 未実装（StrategyEngine 実装とテストが未着手）。 |
| strategy_plugin_contract | Strategy Plugin Protocol への準拠を静的に検証する。 | `pytest -k "strategy_plugin_contract"` | 未実装（Protocol テスト未整備）。 |
| feature_context_contract | FeatureContext / FeatureFrameView の契約と `metadata.required_features` キー表との一致を検証する。 | `pytest -k "feature_context_contract and smoke"` | 雛形追加（smoke skip、FeatureContext 実装待ち）。 |
| strategy_manifest | `strategy_manifest.yaml` のバリデーションとガバナンス手順の検証。 | `pytest -k "strategy_manifest"` | 未実装（Manifest テスト未整備）。 |
| strategy_registry | Strategy Registry のロードと Fail-Fast 振る舞いを検証する。 | `pytest -k "strategy_registry"` | 未実装（Registry テスト未整備）。 |
| ticket_builder | チケット JSON 整形と HITL UX の要件を検証する。 | `pytest -k "ticket_builder"` | 未実装（Ticket Builder 実装／テストが未整備）。 |
| json_schema_validation | 取引状態およびアカウント関連 JSON Schema の整合性を検証する。 | `pytest -k "json_schema_validation"` | 実装済（`tests/schema/test_json_schema_validation.py`）。 |

> **共有スプレッドシートについて**: 現在リポジトリ内に指定されたトラッキングスプレッドシートは存在しないため、本表を Ops／Codex 共通の参照元とする。
