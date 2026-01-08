# Implementation Packet: PKG-STRAT-IFACE-01

## メタデータ
- Epic: EP-02 Strategy Determinism
- Packet範囲: Strategy Plugin Protocol/ベースクラス整備
- 参照セクション: §0.6.11, §3.5.5
- 依頼Issue/PR: <TBD>
- 作成日: 2025-03-12
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250312_pkg-strat-iface-01/

## 1. 目的と背景
- KPI/リスク影響: Backtest/Live決定論一致率>99.5%、StrategyRegistry起動時に契約逸脱が残らないこと。
- ユーザストーリー/Runbook整合: Runbook `GOV-STRAT-01` と detailed_design §3.5.5 で定義されたプラグイン契約をコード化し、Codex レビュー時に署名揺れが再発しない状態を作る。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| src/strategies/base.py | `StrategyContext` スタブと `StrategyPluginProtocol` を定義。`determinism_key`/`context`/`generate_signals()` を必須属性として明文化し、後方互換の `Strategy` エイリアスを維持。 | `pytest -k strategy_plugin_contract` | N/A |
| src/strategies/registry.py | `register_plugin` で Protocol 遵守と `determinism_key` の存在を検証。`run_all` は `generate_signals` を優先呼び出しし、欠落時は従来の `evaluate` にフォールバック。 | `pytest -k strategy_registry` | N/A |
| tests/unit/test_strategy_registry.py | プロトコルエクスポートと `determinism_key` 必須検証のユニットテストを追加。 | `pytest tests/unit/test_strategy_registry.py -k determinism` | N/A |
| docs/implementation_packets/20250312_strat_plugin_contract.md | 本ドキュメントをテンプレ準拠で発行し、受入条件を整理。 | N/A | N/A |

## 3. チェックリスト
- [x] 設計整合: detailed_design §3.5.5 のフィールド表を参照し、コードレビューで差分確認。
- [x] テスト実行: `poetry run pytest tests/unit/test_strategy_registry.py -k determinism`（`reports/implementation/20250312_pkg-strat-iface-01/logs/pytest_strategy_registry_determinism_20250331.log`）
- [x] 監査ログ検証: StrategyRegistry ログに `determinism_key_missing` エラーを追加。
- [x] Rollback手順記載: docs/governance/feature_flag_register.md に本 IF の影響無しを記録。
- [x] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-STRAT-IFACE-01.md を作成し、CLI スナップショットを添付。

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/PKG-STRAT-IFACE-01.md に StrategyRegistry 登録ログを貼付予定。
- メトリクス: reports/implementation/20250312_pkg-strat-iface-01/metrics/ に determinism チェック件数を保存。
- ログ: reports/implementation/20250312_pkg-strat-iface-01/logs/ に pytest 実行ログを保存。

## 5. リスクと依存関係
- 依存Packet: PKG-STRAT-DETERMINISM-01（Registry 決定論ハーネス拡張）
- 懸念事項/Acceptable Degradationへの影響: 既存プラグインが `determinism_key` を未実装の場合に登録失敗となるため、M1 以前の PoC プラグインへ周知が必要。

## 6. アクションアイテム
- Runbook更新ID: RUN-STRAT-CTX-02（StrategyContext スナップショット取得手順）
- Follow-upチケット: OPS-74 StrategyRegistry ログ整備、RES-48 Codex プラグインテンプレ更新

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-12 | Codex Liaison | 初版作成 |
