# Implementation Packet: PKG-JSON-SCHEMA-01

## メタデータ
- Epic: EP-05 Schema Governance
- Packet範囲: JSON Schema バリデーションテスト維持
- 参照セクション: detailed_design_fx_signal_tool_v1.md §4.4, §16.5
- 依頼Issue/PR: <TBD>
- 作成日: 2025-03-15
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250315_pkg-json-schema-01/

## 1. 目的と背景
- KPI/リスク影響: `docs/schemas/`配下の公式JSON Schemaが最新状態であり、`pytest -k json_schema_validation`でRunbook/監査証跡（§4.4設定ファイル、§16.5 JSON Schemaリファレンス）をカバーしていることを保証。Schema不整合は注文/ガバナンスログ破損につながる。
- ユーザストーリー/Runbook整合: `RUN-BROKER-API-02`や`RUN-OPS-LOG-01`で要求される監査証跡を自動検証し、Codex PRレビューでSchema差分を提示する。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| tests/schema/test_json_schema_validation.py | 既存テストへPacket IDコメントと追加Schema TODOを追記（別差分で対応予定）。 | `pytest -k "json_schema_validation"` | N/A |
| docs/implementation_packets/20250315_json_schema_validation.md | 本Packet作成。Schemaリファレンス参照を整理。 | N/A | N/A |

## 3. チェックリスト
- [ ] 設計整合: detailed_design_fx_signal_tool_v1.md §4.4, §16.5 をレビュー
- [ ] テスト実行: `poetry run pytest -k "json_schema_validation"`
- [ ] 監査ログ検証: `docs/schemas/`更新時に`reports/validation_log/`へ差分レポートを保存
- [ ] Rollback手順記載: docs/governance/feature_flag_register.mdへSchema差戻し手順を追記
- [ ] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-JSON-SCHEMA-01.md

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
