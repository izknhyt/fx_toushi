# Implementation Packet: PKG-STRAT-REGISTRY-01

## メタデータ
- Epic: EP-02 Strategy Determinism
- Packet範囲: Strategy Registry Fail-Fast と determinism hash テスト
- 参照セクション: detailed_design_fx_signal_tool_v1.md §3.2（StrategyEngine/Registry）, §15.2
- 依頼Issue/PR: <TBD>
- 作成日: 2025-03-15
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250315_pkg-strat-registry-01/

## 1. 目的と背景
- KPI/リスク影響: StrategyRegistryがManifest差分と決定論ハッシュをFail-Fastする設計（§3.2 APIインターフェース表、§15.2 EP02-T2）をテスト化し、誤登録によるシグナル逸脱を防止。
- ユーザストーリー/Runbook整合: `StrategyRegistry.execute_all`がOps監査ログに`strategy.determinism`イベントを出力する設計を再現し、CIで`StrategyRegistrationError`コード体系を検証する。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| tests/unit/test_strategy_registry_placeholder.py | `pytest.mark.strategy_registry`のxfailテストを追加し、Manifest不整合・deterministic_hash検証TODOを記載。 | `pytest -k "strategy_registry"` | N/A |
| docs/implementation_packets/20250315_strategy_registry.md | 本Packet作成。設計参照とログ要件を整理。 | N/A | N/A |

## 3. チェックリスト
- [ ] 設計整合: detailed_design_fx_signal_tool_v1.md §3.2, §15.2 をレビュー
- [ ] テスト実行: `poetry run pytest -k "strategy_registry"`
- [ ] 監査ログ検証: `logs/strategy/registry.log` に`strategy.determinism`イベントが生成されることを確認
- [ ] Rollback手順記載: docs/runbooks/STRAT-M1-VALIDATION.mdへRegistry Fail-Fast時の対処を追記
- [ ] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-STRAT-REGISTRY-01.md

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/PKG-STRAT-REGISTRY-01.md
- メトリクス: reports/implementation/20250315_pkg-strat-registry-01/metrics/
- ログ: reports/implementation/20250315_pkg-strat-registry-01/logs/

## 5. リスクと依存関係
- 依存Packet: PKG-STRAT-MANIFEST-01, PKG-STRAT-DETERMINISM-01
- 懸念事項/Acceptable Degradationへの影響: Registryが不正戦略をロードすると、Ops Boardでのガード判定が崩れ、誤注文リスクが増大。

## 6. アクションアイテム
- Runbook更新ID: STRAT-M1-VALIDATION
- Follow-upチケット: STRAT-REGISTRY-HASH（deterministic_hash生成実装）

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-15 | Codex Liaison | 初版作成 |
