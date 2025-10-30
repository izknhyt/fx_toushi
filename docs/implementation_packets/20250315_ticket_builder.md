# Implementation Packet: PKG-TICKET-BUILDER-01

## メタデータ
- Epic: EP-04 Ticket Clarity
- Packet範囲: TicketBuilder チェックリスト / GateState連携テスト整備
- 参照セクション: detailed_design_fx_signal_tool_v1.md §3.5.2, §3.16
- 依頼Issue/PR: <TBD>
- 作成日: 2025-03-15
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250315_pkg-ticket-builder-01/

## 1. 目的と背景
- KPI/リスク影響: GateState受け渡しとChecklist生成が設計（§3.5.2 GateState伝播、§3.16 TicketBuilder）通りに行われるかテスト化し、HITLダブルエントリーフロー崩壊を防ぐ。誤ったチケットJSONはRunbook `RUN-HITL-01`を破綻させる。
- ユーザストーリー/Runbook整合: `TicketBuilder.build`がSpread/Reduce-Only/Double entry必須項目を反映することをCIで確認し、`tradectl board`表示と監査ログが一致することを保証。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| tests/unit/test_ticket_builder_placeholder.py | `pytest.mark.ticket_builder`のxfailテストを追加し、GateStateスライス統合とChecklist検証TODOを明記。 | `pytest -k "ticket_builder"` | N/A |
| docs/implementation_packets/20250315_ticket_builder.md | 本Packet作成。GateState伝播要件とRunbook参照を整理。 | N/A | N/A |

## 3. チェックリスト
- [ ] 設計整合: detailed_design_fx_signal_tool_v1.md §3.5.2, §3.16 をレビュー
- [ ] テスト実行: `poetry run pytest -k "ticket_builder"`
- [ ] 監査ログ検証: `ticket.issued`イベントにSpread/Checklist情報が含まれることを確認
- [ ] Rollback手順記載: docs/runbooks/RUN-HITL-01.mdへFallback操作を追記
- [ ] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-TICKET-BUILDER-01.md

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/PKG-TICKET-BUILDER-01.md
- メトリクス: reports/implementation/20250315_pkg-ticket-builder-01/metrics/
- ログ: reports/implementation/20250315_pkg-ticket-builder-01/logs/

## 5. リスクと依存関係
- 依存Packet: PKG-STRAT-REGISTRY-01（GateState入力）, PKG-STRAT-MANIFEST-01（Watchlist整合）
- 懸念事項/Acceptable Degradationへの影響: TicketChecklist欠落はHITLオペレーション停止や監査不備を招く。

## 6. アクションアイテム
- Runbook更新ID: RUN-HITL-01, RUN-OPS-AGENDA-01
- Follow-upチケット: TICKET-BUILDER-CHECKS（Checklist自動検証実装）

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-03-15 | Codex Liaison | 初版作成 |
