# Implementation Packet: PKG-CONFIG-SCHEMA-01

## メタデータ
- Epic: EP-01 Config Governance
- Packet範囲: Config schema smoke 検証導線整備
- 参照セクション: detailed_design_fx_signal_tool_v1.md §0.6.8, §4.4
 - 依頼Issue/PR: docs/change_requests/20250318_packet_backlog.md#pkg-config-schema-01
- 作成日: 2025-03-15
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250315_pkg-config-schema-01/

## 1. 目的と背景
- KPI/リスク影響: Config雛形とJSON Schemaの乖離を早期検知し、`pytest -k config_schema_smoke`が設計で定義された前提（§0.6.8-#6, §4.4）を守る。逸脱時はBoardMode/リスク閾値に誤設定が伝搬するリスクを抑止。
- ユーザストーリー/Runbook整合: Runbook `GOV-STRAT-01` と `RUN-DATA-05/06` が参照する設定ファイルの正本性を担保し、CodexレビューでSchema検証ログを必須化する。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| tests/config/test_config_schema_smoke.py | Config雛形とJSON Schemaの突合テストを実装。 | `pytest -k "config_schema_smoke"` | N/A |
| docs/implementation_packets/20250315_config_schema_smoke.md | 本Packet作成。設計参照とテスト要件を明文化。 | N/A | N/A |

## 3. チェックリスト
- [x] 設計整合: detailed_design_fx_signal_tool_v1.md §0.6.8, §4.4 をレビューし、対象ファイル／Runbook参照を確認
- [x] テスト実行: `pytest tests/config/test_config_schema_smoke.py -k config_schema_smoke`（Signal 11 回避のためファイル指定で実施）
- [x] 監査ログ検証: `reports/validation_log/PKG-CONFIG-SCHEMA_20250319.md` にコマンド出力を保存
- [x] Rollback手順記載: docs/governance/feature_flag_register.md ではなく `docs/runbooks/CONFIG-SCAFF-01.md` に schema-smoke 必須手順が既に記載されていることを確認
- [x] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-CONFIG-SCHEMA-01.md（2025-03-19更新）

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/PKG-CONFIG-SCHEMA-01.md
- メトリクス: reports/implementation/20250315_pkg-config-schema-01/metrics/
- ログ: reports/implementation/20250315_pkg-config-schema-01/logs/

## 5. リスクと依存関係
- 依存Packet: CONFIG-SCAFF-01（config雛形整備）
- 懸念事項/Acceptable Degradationへの影響: Schema検証未整備のままリリースすると、GateState/Risk設定がRunbook要件から逸脱する可能性がある。

## 6. アクションアイテム
- Runbook更新ID: GOV-STRAT-01, RUN-DATA-05
- Follow-upチケット: CONFIG-SCHEMA-AUTO-VALIDATOR（CIへの自動組み込み）

## 7. フォローアップ
- [x] Feature Flag tracker: `docs/risk_review/20250318_prelaunch.md` のチェックリストを更新し、`config/feature_flags.yaml` + `pytest -k feature_flags` をEvidence化（2025-11-17）。
- [x] Trader Sign-off: `docs/trader_signoff/OPS-READINESS-20250318.md` にAC-02/03/04/05/06結果を反映（2025-11-17）。

## 8. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-15 | Codex Liaison | 初版作成 |
| 2025-11-17 | Codex Liaison | Follow-up節を追加し、OPS-READINESS Sign-offへのリンクを明記 |
