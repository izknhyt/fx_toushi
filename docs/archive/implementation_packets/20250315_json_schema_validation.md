# Implementation Packet: PKG-JSON-SCHEMA-01

## メタデータ
- Epic: EP-05 Schema Governance
- Packet範囲: JSON Schema バリデーションテスト維持
- 参照セクション: detailed_design_fx_signal_tool_v1.md §4.4, §16.5
 - 依頼Issue/PR: docs/change_requests/20250318_packet_backlog.md#pkg-json-schema-01
- 作成日: 2025-03-15
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250315_pkg-json-schema-01/

## 1. 目的と背景
- KPI/リスク影響: `docs/schemas/`配下の公式JSON Schemaが最新状態であり、`pytest -k json_schema_validation`でRunbook/監査証跡（§4.4設定ファイル、§16.5 JSON Schemaリファレンス）をカバーしていることを保証。Schema不整合は注文/ガバナンスログ破損につながる。
- ユーザストーリー/Runbook整合: `RUN-BROKER-API-02`や`RUN-OPS-LOG-01`で要求される監査証跡を自動検証し、Codex PRレビューでSchema差分を提示する。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| tests/jsonschema/test_domain_schemas.py, tests/jsonschema/test_schema_integrity.py | JSON Schemaバリデーションテストを新設し、各ドメインスキーマ＋全体整合性を自動検証。 | `pytest tests/jsonschema -k "json_schema_validation"` | N/A |
| docs/implementation_packets/20250315_json_schema_validation.md | 本Packet作成。Schemaリファレンス参照を整理。 | N/A | N/A |
| src/core/schema_registry.py, src/interfaces/cli/schema_validate.py, tests/config/test_config_schema_smoke.py | `referencing.Registry`ベースのスキーマリゾルバを実装し、RefResolver依存を撤去。 | `poetry run schema-validate config/profiles/backtest.yaml --schema docs/schemas/cfg.schema.json` | jsonschema_referencing_registry |

## 3. チェックリスト
- [x] 設計整合: detailed_design_fx_signal_tool_v1.md §4.4, §16.5 をレビュー
- [x] テスト実行: `pytest tests/jsonschema -k "json_schema_validation"`
- [x] 監査ログ検証: `reports/validation_log/PKG-JSON-SCHEMA_20250319.md`にCLI出力を保存
- [x] Rollback手順記載: docs/governance/feature_flag_register.mdへSchema差戻し手順を追記
- [x] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-JSON-SCHEMA-01.md（2025-03-19更新）

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/PKG-JSON-SCHEMA-01.md
- メトリクス: reports/implementation/20250315_pkg-json-schema-01/metrics/
- ログ: reports/implementation/20250315_pkg-json-schema-01/logs/

## 5. リスクと依存関係
- 依存Packet: PKG-CONFIG-SCHEMA-01, PKG-STRAT-MANIFEST-01
- 懸念事項/Acceptable Degradationへの影響: Schemaの後方互換性が欠落すると、Ops自動化・監査報告が停止する。

## 6. アクションアイテム
- Runbook更新ID: RUN-BROKER-API-02, RUN-OPS-LOG-01
- Follow-upチケット: JSON-SCHEMA-AUTOGEN（Schema更新自動生成）

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-15 | Codex Liaison | 初版作成 |
| 2025-03-22 | Codex Liaison | referencingレジストリ化、schema-validate CLIログ更新、Rollback手順（Feature Flag Register）追記 |
