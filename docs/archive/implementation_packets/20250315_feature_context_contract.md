# Implementation Packet: PKG-FEATURE-CONTEXT-01

## メタデータ
- Epic: EP-02 Strategy Determinism
- Packet範囲: FeatureContext / FeatureFrameView 契約テスト強化
- 参照セクション: detailed_design_fx_signal_tool_v1.md §3.3.2, §3.5.5
 - 依頼Issue/PR: docs/change_requests/20250318_packet_backlog.md#pkg-feature-context-01
- 作成日: 2025-03-15
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250315_pkg-feature-context-01/

## 1. 目的と背景
- KPI/リスク影響: Manifest `required_features` と FeaturePipeline `available_keys` の不一致をFail-Fastし、StrategyEngineがFeature不足で停止する設計（§3.3.2, §3.5.5）を担保する。
- ユーザストーリー/Runbook整合: CodexがFeatureを追加する際のチェックリスト（Runbook `GOV-STRAT-01` Feature差分是正）と連携し、`pytest -k "feature_context_contract and smoke"`が常にCI監視される状態を維持。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| docs/implementation_packets/20250315_feature_context_contract.md | 本Packet作成。既存スモークテストと設計参照を同期。 | N/A | N/A |
| tests/smoke/test_feature_context_contract.py | 既存スモークテストへPacket IDコメントとRunbook参照を追記（別差分で対応予定）。 | `pytest -k "feature_context_contract and smoke"` | N/A |

## 3. チェックリスト
- [x] 設計整合: detailed_design_fx_signal_tool_v1.md §3.3.2, §3.5.5（2025-03-19再確認、reports/validation_log/PKG-STRAT-GOV_20250319.md参照）
- [x] テスト実行: `pytest -k "feature_context_contract and smoke"`（reports/validation_log/PKG-STRAT-GOV_20250319.md）
- [x] 監査ログ検証: `reports/validation_log/PKG-STRAT-GOV_20250319.md`で`strategy_manifest.watchlist_feature_missing`が未出力であることを確認
- [x] Rollback手順記載: docs/runbooks/GOV-STRAT-01.md 事前準備/チェックリストへLifecycle/Watchlistテスト項目を追加
- [x] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-FEATURE-CONTEXT-01.md（Ops Manager下書き済み）

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/PKG-FEATURE-CONTEXT-01.md
- メトリクス: reports/implementation/20250315_pkg-feature-context-01/metrics/
- ログ: reports/implementation/20250315_pkg-feature-context-01/logs/

## 5. リスクと依存関係
- 依存Packet: PKG-STRAT-IFACE-01, PKG-STRAT-DETERMINISM-01
- 懸念事項/Acceptable Degradationへの影響: Feature不足がLive移行時に検出されず、SignalEngineが不安定化するリスク。

## 6. アクションアイテム
- Runbook更新ID: GOV-STRAT-01
- Follow-upチケット: FEATURE-CTX-AUTO-DIFF（ManifestとFeature差分アラート自動化）

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-15 | Codex Liaison | 初版作成 |
