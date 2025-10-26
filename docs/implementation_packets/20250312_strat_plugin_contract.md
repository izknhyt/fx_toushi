# Implementation Packet: PKG-STRAT-IFACE-01

## メタデータ
- Epic: EP-02 Strategy Determinism
- Packet範囲: Strategy Plugin Protocol/ベースクラス整備
- 参照セクション: §0.6.11, §3.5.5, §15.2
- 依頼Issue/PR: <TBD>
- 作成日: 2025-03-12
- 作成者: Codex Liaison（SEレビュー指摘#7反映）
- エビデンス格納先: reports/implementation/20250312_pkg-strat-iface-01/

## 1. 目的と背景
- KPI/リスク影響: Backtest/Live決定論一致率>99.5%、StrategyRegistry起動時の契約逸脱Fail-Fast。署名揺らぎによる誤発注・テスト不一致を回避。
- ユーザストーリー/Runbook整合: Runbook `GOV-STRAT-01`と§3.5.5で定義したプラグインチェックリストを実装に落とし込み、Codex PRレビューの自動チェックを可能にする。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| src/strategies/base.py | `StrategyPluginProtocol`/`StrategyMetadata` dataclass/`StrategyContext`型ヒントのスタブを追加。`Protocol`で`evaluate/required_warmup_bars/cooldown_bars`を宣言し、決定論シード伝播をdocstringに明記。 | `pytest -k strategy_plugin_contract` | N/A |
| src/strategies/registry.py | Manifestロード時にProtocol準拠検査・`StrategyRegistrationError(code='contract_violation')`のFail-Fast実装。 | `pytest -k strategy_registry` | N/A |
| tests/unit/test_strategy_plugin_contract.py | Protocol準拠/seed決定論/ログ付与のスモークテストを追加。 | `pytest -k strategy_plugin_contract` | N/A |
| docs/trader_signoff/PKG-STRAT-IFACE-01.md | CLIスナップショット/Runbookリンク/承認サイン欄を作成。 | `tradectl board --view strategy --save-snapshot ...` | N/A |

## 3. チェックリスト
- [ ] 設計整合: §3.5.5・§0.6.11と照合し、Protocol/ログ要件を満たす
- [ ] テスト実行: `poetry run pytest -k "strategy_plugin_contract or strategy_registry"`
- [ ] 監査ログ検証: `logs/signals/raw/<date>.jsonl`に`seed`/`feature_sample`が記録されていることを確認
- [ ] Rollback手順記載: docs/governance/feature_flag_register.mdへ「Strategy Plugin Contract」項目を追記
- [ ] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-STRAT-IFACE-01.md にスクリーンショット・承認サイン

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/PKG-STRAT-IFACE-01.md を参照
- メトリクス: reports/implementation/20250312_pkg-strat-iface-01/metrics/
- ログ: reports/implementation/20250312_pkg-strat-iface-01/logs/

## 5. リスクと依存関係
- 依存Packet: `PKG-BOOT-01`（poetry環境整備）, `SRC-SCAFF-01`（srcディレクトリ雛形）
- 懸念事項/Acceptable Degradationへの影響: Protocol導入により未対応プラグインは起動時に停止するため、Manifestの`enabled`初期値確認が必須。Runbook `RUN-RISK-02`でGuarded移行手順を確認してから有効化する。

## 6. アクションアイテム
- Runbook更新ID: GOV-STRAT-01, RUN-SIGNAL-02
- Follow-upチケット: `DOC-RUNBOOK-ALIGN-02`（テンプレ更新）, `OPS-58`（Issueテンプレ整備）

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-12 | Codex Liaison | 初版作成（SEレビュー#7是正） |
