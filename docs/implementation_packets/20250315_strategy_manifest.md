# Implementation Packet: PKG-STRAT-MANIFEST-01

## メタデータ
- Epic: EP-02 Strategy Determinism
- Packet範囲: Strategy Manifest 検証・ガバナンス運用
- 参照セクション: detailed_design_fx_signal_tool_v1.md §4.4.1, §6.7
- 依頼Issue/PR: <TBD>
- 作成日: 2025-03-15
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250315_pkg-strat-manifest-01/

## 1. 目的と背景
- KPI/リスク影響: Manifest差分がConfig Governanceチェックリスト（§6.7）と一致していることをテストで保証し、戦略順序・優先度の逸脱を防止。Schema違反はStrategyEngine起動不能となるため、早期検出が必須。
- ユーザストーリー/Runbook整合: `GOV-STRAT-01`承認フローと`RUN-SIGNAL-02`ウォッチリスト調整手順を自動化し、`poetry run pytest -k "strategy_manifest"`に証跡を集約。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| tests/unit/test_strategy_manifest_placeholder.py | `pytest.mark.strategy_manifest`のxfailテストを追加し、Schema検証・watchlist制約テストのTODOを明記。 | `pytest -k "strategy_manifest"` | N/A |
| docs/implementation_packets/20250315_strategy_manifest.md | 本Packet作成。Schema参照とRunbook同期を明記。 | N/A | N/A |

## 3. チェックリスト
- [ ] 設計整合: detailed_design_fx_signal_tool_v1.md §4.4.1, §6.7 をレビュー
- [ ] テスト実行: `poetry run pytest -k "strategy_manifest"`
- [ ] 監査ログ検証: `strategy_manifest.watchlist_feature_missing` / `strategy_manifest.symbol_filtered` ログの有無を確認
- [ ] Rollback手順記載: docs/runbooks/GOV-STRAT-01.md、RUN-SIGNAL-02へ影響範囲を追記
- [ ] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-STRAT-MANIFEST-01.md

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/PKG-STRAT-MANIFEST-01.md
- メトリクス: reports/implementation/20250315_pkg-strat-manifest-01/metrics/
- ログ: reports/implementation/20250315_pkg-strat-manifest-01/logs/

## 5. リスクと依存関係
- 依存Packet: PKG-CONFIG-SCHEMA-01, PKG-FEATURE-CONTEXT-01
- 懸念事項/Acceptable Degradationへの影響: Manifest不整合はStrategyRegistryロード失敗やWatchlist過多によるガバナンス違反を招く。

## 6. アクションアイテム
- Runbook更新ID: GOV-STRAT-01, RUN-SIGNAL-02
- Follow-upチケット: STRAT-MANIFEST-VALIDATOR（CI組み込み）

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-15 | Codex Liaison | 初版作成 |
