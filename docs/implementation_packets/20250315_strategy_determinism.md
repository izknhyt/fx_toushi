# Implementation Packet: PKG-STRAT-DETERMINISM-01

## メタデータ
- Epic: EP-02 Strategy Determinism
- Packet範囲: StrategyEngine決定論テストハーネス
- 参照セクション: detailed_design_fx_signal_tool_v1.md §3.5.2, §3.5.5, §15.2
 - 依頼Issue/PR: docs/change_requests/20250318_packet_backlog.md#pkg-strat-determinism-01
- 作成日: 2025-03-15
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250315_pkg-strat-determinism-01/

## 1. 目的と背景
- KPI/リスク影響: Backtest/Paper/Liveのシグナル一致率>99.5%を保証（§3.5.2シグナル疑似コード、§3.5.5 StrategyContext契約、§15.2 EP-02ロードマップ）。決定論崩壊はOpsレビュー（Runbook `STRAT-M1-VALIDATION`）の判定根拠を失わせるため重大リスク。
- ユーザストーリー/Runbook整合: StrategyRegistryの`deterministic_seed`伝搬と`StrategyContext.watchlist`不変性をテストで再現し、`tradectl benchmark replay`証跡をOpsへ共有する。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| tests/integration/test_strategy_determinism.py | 決定論リグレッションを実装し、Seed/ハッシュの一致を検証。 | `pytest -k "strategy_determinism"` | N/A |
| tests/integration/test_strategy_engine.py | `DeterministicExecutionModel`を用いたSpread状態別TTL/バッジ検証を追加。`ModeContext.deterministic_seed`を共有してBacktest/Paper/Live間で同一サンプルが再現されることを確認。 | `pytest -k "strategy_engine and execution_model"` | N/A |
| docs/implementation_packets/20250315_strategy_determinism.md | 本Packet作成。決定論KPIとRunbook整合を整理。 | N/A | N/A |

## 3. チェックリスト
- [x] 設計整合: detailed_design_fx_signal_tool_v1.md §3.5.2, §3.5.5, §15.2 をレビュー（記録: `reports/validation_log/PKG-STRAT-DETERMINISM_20250319.md`）
- [x] テスト実行: `pytest tests/integration/test_strategy_engine.py tests/integration/test_strategy_determinism.py -vv`
- [x] 監査ログ検証: `metrics/benchmark_replay.jsonl` にDigest `b983fb3e4a67f17ba39d0f97`を追記し、`reports/validation_log/PKG-STRAT-DETERMINISM_20250319.md`へリンク
- [x] Rollback手順記載: docs/runbooks/STRAT-M1-VALIDATION.md §3.1に決定論リプレイ確認とStop条件を追加
- [x] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-STRAT-DETERMINISM-01.md（2025-03-19下書き更新）

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/PKG-STRAT-DETERMINISM-01.md
- メトリクス: reports/implementation/20250315_pkg-strat-determinism-01/metrics/
- ログ: reports/implementation/20250315_pkg-strat-determinism-01/logs/

## 5. リスクと依存関係
- 依存Packet: PKG-STRAT-IFACE-01（Protocol実装）
- 懸念事項/Acceptable Degradationへの影響: 決定論欠落時はBacktest結果がLiveへ適用できず、HITL承認判断が無効化される。

## 6. アクションアイテム
- Runbook更新ID: STRAT-M1-VALIDATION
- Follow-upチケット: STRAT-DETERMINISM-CI（再現ハーネスCI導入）

## 7. SPRTチューニングフォローアップ（§11.1 リスク#3対応）
- **背景**: detailed_design_fx_signal_tool_v1.md §11.1ではSPRT閾値が不安定なまま戦略追加が進むリスクが指摘されている。本Packetでは決定論インフラを整備済みのため、ウォームアップ期間とベイズ更新ルールをここに追記する。
- **ウォームアップ**: `strategy_manifest.yaml::entry.lifecycle.warmup_bars`を`14d ≒ 10,080 bars`で固定し、`StrategyEngine`は`entry.lifecycle.status='warming'`のうちは`SprtEvaluator`を`stop=False`で返すよう`src/risk/sprt.py`を更新する。ウォームアップ完了後にのみ`SprtResult.stop=True/False`を評価する。
- **ベイズ更新**: `sprt.py`へ`alpha=0.05`,`beta=0.1`の参照実装を追加済み。M2以降でPosterior更新を導入するため、`reports/implementation/20250315_pkg-strat-determinism-01/sprt_calibration.md`をEvidence台帳とし、`tradectl benchmark replay --strict`のシードハッシュを併記する。
- **Runbookリンク**: `docs/runbooks/STRAT-M1-VALIDATION.md`に「SPRTウォームアップチェックリスト」を追加予定（Follow-up: STRAT-DETERMINISM-CI）。
- **リスククローズ条件**: 上記EvidenceがOpsレビューでサインされ、`docs/risk_review/20250318_prelaunch.md` §11.1-3に「Closed (PKG-STRAT-DETERMINISM-01 addendum)」と追記されること。

## 8. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-15 | Codex Liaison | 初版作成 |
