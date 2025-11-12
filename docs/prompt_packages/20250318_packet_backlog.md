# Prompt Package: 20250318 Packet Backlog

このドキュメントは`docs/change_requests/20250318_packet_backlog.md`で定義した未着手Packetのプロンプト雛形を集約する。各節はCodexへ渡す要約文・受入条件・参照コマンドを最低限記載しており、実装開始時に該当節をコピー＆修正する。GitHub Issue起票時は下表の仮IDを更新し、`docs/templates/codex_issue.md`のCHK欄に`reports/validation_log/CHK-0.6.9_env_setup_20250318.md`および`docs/runbooks/daily_agenda/2025-03-18.md`へのリンクを添付する。

| Packet | 仮Issue ID | 担当 | 前提CHK |
| --- | --- | --- | --- |
| EP00-P1 / PKG-CONFIG-SCHEMA-01 | OPS-70 | Config Maintainer | CHK-0.6.9-1/2/4 |
| EP01-P1 / PKG-DATA-STATUS-01 | OPS-71 | Data Lead | CHK-0.6.9-1/2 |
| EP02-P1 / PKG-STRAT-DETERMINISM-01 | OPS-72 | Quant Lead | CHK-0.6.9-3/6 |
| EP03-P1 / PKG-TICKET-BUILDER-01 | OPS-73 | Ops Manager | CHK-0.6.9-5/7 |
| EP04-P1 / PKG-WEEKLY-REPORT (※本書ではEP05相当) | OPS-74 | Product Owner | CHK-0.6.9-3/8 |
| PKG-JSON-SCHEMA-01 | OPS-75 | Lead Engineer | CHK-0.6.9-4 |
| PKG-STRAT-MANIFEST-01 | OPS-76 | Quant Lead | CHK-0.6.9-3/5 |
| PKG-STRAT-REGISTRY-01 | OPS-77 | Quant Lead | CHK-0.6.9-3/6 |
| PKG-FEATURE-CONTEXT-01 | OPS-78 | Data Lead | CHK-0.6.9-6 |
| PKG-TRADECTL-STATUS-RESYNC-01 | OPS-79 | Ops Manager | CHK-0.6.9-5/7 |

## PKG-CONFIG-SCHEMA-01
- **目的**: `pytest -k config_schema_smoke` で `config/` 雛形とJSON Schemaの整合性を確認できるようにする。
- **主な作業**: `docs/schemas/*.json` の参照を`tests/schema/test_json_schema_validation.py`へ接続し、`config/README.md`のRunbook参照を最新化。
- **受入条件**: `poetry run pytest -k config_schema_smoke`、`poetry run schema-validate config --schema docs/schemas/config_bundle.schema.json`。
- **進捗 (2025-03-19)**: `tests/config/test_config_schema_smoke.py`で各YAML×JSON Schemaを検証し、`reports/validation_log/PKG-CONFIG-SCHEMA_20250319.md`に`schema-validate`出力を記録。`pytest -k config_schema_smoke`はSignal 11のためモジュール指定で代替実施。

## PKG-DATA-STATUS-01
- **目的**: `tradectl data status --log-stage-eval` を自動テストで追跡し、`metrics/rate_limit_window.jsonl`の`stage_eval`記録を保証。
- **主な作業**: `tests/cli/test_data_status_cli.py` を実装、`RUN-DATA-05`/`RUN-DATA-06`リンク付きのログ生成。
- **受入条件**: `poetry run pytest -k "data_status_cli"`、`reports/validation_log/AC-45_sla_<date>.md`へログ追記。

## PKG-FEATURE-CONTEXT-01
- **目的**: `FeatureContext`/`FeatureFrameView`の契約をテスト化し、`metadata.required_features`差分を検知。
- **主な作業**: `tests/smoke/test_feature_context_contract.py`のTODO解消、`src/features/pipeline.py`スタブ更新。
- **受入条件**: `poetry run pytest -k "feature_context_contract and smoke"`、`docs/implementation_packets/20250315_feature_context_contract.md`のチェックリスト完了。
- **進捗 (2025-03-19)**: `pytest -k "feature_context_contract and smoke"`を実行し証跡を `reports/validation_log/PKG-STRAT-GOV_20250319.md` に保存。チェックリストのテスト項目を消化。

## PKG-JSON-SCHEMA-01
- **目的**: `tests/schema/test_json_schema_validation.py`で定義済みスキーマのバックログを最新状態に保つ。
- **主な作業**: `docs/schemas/`配下の追加・更新、`tests/schema/...`のケース拡張。
- **受入条件**: `poetry run pytest -k json_schema_validation`、`reports/implementation/20250315_pkg-json-schema-01/logs/`にCLI出力を保存。
- **進捗 (2025-03-19)**: `tests/jsonschema/test_domain_schemas.py`＋`tests/jsonschema/test_schema_integrity.py`を新設し、`reports/validation_log/PKG-JSON-SCHEMA_20250319.md`に証跡を保存。

## PKG-STRAT-DETERMINISM-01
- **目的**: StrategyEngineの決定論テストを整備し、Backtest/Paper/Liveで同一出力となることを保証。
- **主な作業**: `tests/integration/test_strategy_determinism.py`のxfail解消、`src/strategies/registry.py`の`determinism_seed`処理。
- **受入条件**: `poetry run pytest -k strategy_determinism`、`reports/validation_log/CHK-0.6.9_strategy_contract_*.md`へエビデンス追記。
- **進捗 (2025-03-19)**: `tests/integration/test_strategy_determinism.py`を実装し、`reports/validation_log/PKG-STRAT-DETERMINISM_20250319.md`＋`metrics/benchmark_replay.jsonl`にエビデンスを集約。`pytest -k strategy_determinism`はpytestバグで不安定なため、当面は明示的ファイル指定で代替する。

## PKG-STRAT-MANIFEST-01
- **目的**: `strategy_manifest.yaml`のガバナンス検証（watchlist/有効期限チェック）を自動化。
- **主な作業**: `tests/unit/test_strategy_manifest.py`整備、`docs/runbooks/GOV-STRAT-01.md`リンク更新。
- **受入条件**: `poetry run pytest -k strategy_manifest`、`reports/implementation/20250315_pkg-strat-manifest-01/metrics/`へ結果保存。
- **進捗 (2025-03-19)**: `tests/unit/test_strategy_manifest_lifecycle.py`でウォッチリストおよびライフサイクル検証を追加済み（`reports/validation_log/PKG-STRAT-GOV_20250319.md`）。

## PKG-STRAT-REGISTRY-01
- **目的**: Strategy Registryロード順とFail-Fast挙動を保証し、重複/未登録プラグインを即座に検出。
- **主な作業**: `tests/unit/test_strategy_registry.py`、`src/strategies/registry.py`の`determinism_key`ロジック更新。
- **受入条件**: `poetry run pytest -k strategy_registry`、`reports/implementation/20250315_pkg-strat-registry-01/logs/`。
- **進捗 (2025-03-19)**: `tests/unit/test_strategy_registry_contracts.py`で重複登録/メタデータ不一致/未登録プラグインのFail-Fastを検証（`reports/validation_log/PKG-STRAT-GOV_20250319.md`）。

## PKG-TICKET-BUILDER-01
- **目的**: GateState→TicketChecklist伝搬とSpreadダッシュボード表示の整合性を担保。
- **主な作業**: `tests/unit/test_ticket_builder.py`拡張、`GateState`スキーマとの整合確認。
- **受入条件**: `poetry run pytest -k ticket_builder`、`docs/trader_signoff/PKG-TICKET-BUILDER-01.md`でサイン。
- **進捗 (2025-03-19)**: `tests/unit/test_ticket_builder.py`＋`tests/unit/test_ticket_builder_gate_state.py`でGateState/Badge/リスクメタデータを検証。`reports/validation_log/PKG-TICKET-BUILDER_20250319.md`とRunbook更新を完了。
- **優先度メモ (2025-03-19)**: GateState.Lifecycle更新後のChecklist伝搬差分を確認するため、PKG-STRAT-DETERMINISM-01着手と並行で準備する。

## PKG-TRADECTL-STATUS-RESYNC-01
- **目的**: `tradectl status/resync`系CLIの差分表示と監査ログ連携を実装。
- **主な作業**: `src/interfaces/cli/status.py`/`resync.py`のスタブ実装、`tests/unit/test_cli_status.py`更新。
- **受入条件**: `poetry run pytest tests/unit/test_cli_status.py`、`reports/implementation/20250322_pkg-tradectl-status-resync-01/cli/status_20250318.json`に最新キャプチャ保存。
- **進捗 (2025-03-19)**: `tests/unit/test_cli_status.py`/`tests/unit/test_cli_resync.py`でバナー・ReduceOnly・Resync進捗をカバー。Runbook（RUN-DATA-05/06）と設計§17.3/§17.4にサンプル出力を追記し、`reports/validation_log/PKG-TRADECTL-STATUS-RESYNC_20250319.md`へ証跡を保存。
