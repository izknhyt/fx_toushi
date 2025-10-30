# Implementation Packet: PKG-DATA-STATUS-01

## メタデータ
- Epic: EP-03 Data Reliability
- Packet範囲: `tradectl data status` レート制限ステージ評価テスト整備
- 参照セクション: detailed_design_fx_signal_tool_v1.md §3.0, §3.1.1
- 依頼Issue/PR: <TBD>
- 作成日: 2025-03-15
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250315_pkg-data-status-01/

## 1. 目的と背景
- KPI/リスク影響: DataIngestionのレート制限ステージをRunbook `RUN-DATA-05` に沿って追跡し、`metrics/rate_limit_window.jsonl` の`stage_eval`欠落を防止する（§3.0 CLI一覧、§3.1.1レート制限ステージ評価）。
- ユーザストーリー/Runbook整合: Opsが`tradectl data status --log-stage-eval`を実行した証跡をCIで検証し、Ops Agendaでの承認プロセス（Runbook連携）を自動化する。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| tests/cli/test_data_status_cli.py | `pytest.mark.data_status_cli`でxfailするCLIワークフロー雛形を追加。ステージ評価ログ検証の期待値をコメント化。 | `pytest -k "data_status_cli"` | N/A |
| docs/implementation_packets/20250315_data_status_cli.md | 本Packet作成。設計参照・Runbookリンクを整理。 | N/A | N/A |

## 3. チェックリスト
- [ ] 設計整合: detailed_design_fx_signal_tool_v1.md §3.0, §3.1.1 を確認
- [ ] テスト実行: `poetry run pytest -k "data_status_cli"`
- [ ] 監査ログ検証: `metrics/rate_limit_window.jsonl` 最新行に`stage_eval`が含まれることを確認
- [ ] Rollback手順記載: docs/runbooks/RUN-DATA-05.mdへテスト失敗時のFallbackを追記
- [ ] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-DATA-STATUS-01.md

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/PKG-DATA-STATUS-01.md
- メトリクス: reports/implementation/20250315_pkg-data-status-01/metrics/
- ログ: reports/implementation/20250315_pkg-data-status-01/logs/

## 5. リスクと依存関係
- 依存Packet: RUN-DATA-05運用テンプレ更新（DocOps）
- 懸念事項/Acceptable Degradationへの影響: レート制限ステージが未記録のままOps判断が下ると、RateLimitGuard設定が誤ったまま継続するリスク。

## 6. アクションアイテム
- Runbook更新ID: RUN-DATA-05, RUN-DATA-06
- Follow-upチケット: DATA-OPS-LOG-PIPELINE（stage_eval自動集計）

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-15 | Codex Liaison | 初版作成 |
