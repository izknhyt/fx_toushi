# Implementation Packet: PKG-TICKET-BUILDER-01

## メタデータ
- Epic: EP-04 Ticket Clarity
- Packet範囲: TicketBuilder チェックリスト / GateState連携テスト整備
- 参照セクション: detailed_design_fx_signal_tool_v1.md §3.5.2, §3.16
 - 依頼Issue/PR: docs/change_requests/20250318_packet_backlog.md#pkg-ticket-builder-01
- 作成日: 2025-03-15
- 作成者: Codex Liaison
- エビデンス格納先: reports/implementation/20250315_pkg-ticket-builder-01/

## 1. 目的と背景
- KPI/リスク影響: GateState受け渡しとChecklist生成が設計（§3.5.2 GateState伝播、§3.16 TicketBuilder）通りに行われるかテスト化し、HITLダブルエントリーフロー崩壊を防ぐ。誤ったチケットJSONはRunbook `RUN-HITL-01`を破綻させる。
- ユーザストーリー/Runbook整合: `TicketBuilder.build`がSpread/Reduce-Only/Double entry必須項目を反映することをCIで確認し、`tradectl board`表示と監査ログが一致することを保証。

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| tests/unit/test_ticket_builder.py | TicketBuilderのJSON整形とChecklist統合をテスト。 | `pytest -k "ticket_builder"` | N/A |
| tests/unit/test_ticket_builder_gate_state.py | GateStateのリスク/人手ガードメタデータ反映をテスト。 | `pytest -k "ticket_builder"` | N/A |
| docs/implementation_packets/20250315_ticket_builder.md | 本Packet作成。GateState伝播要件とRunbook参照を整理。 | N/A | N/A |

## 3. チェックリスト
- [x] 設計整合: detailed_design_fx_signal_tool_v1.md §3.5.2, §3.16 をレビュー（証跡: `reports/validation_log/PKG-TICKET-BUILDER_20250319.md`）
- [x] テスト実行: `pytest tests/unit/test_ticket_builder.py tests/unit/test_ticket_builder_gate_state.py -k ticket_builder`
- [x] 監査ログ検証: TicketBuilder payloadの`gate_context`/`badge`メタデータが`ticket.issued`へ伝搬する設計どおりであることをテスト出力で確認
- [x] Rollback手順記載: docs/runbooks/RUN-HITL-01.md §1/§3にBadge/Checklistの対処フローを追記
- [x] Trader Sign-offテンプレ発行: docs/trader_signoff/PKG-TICKET-BUILDER-01.md（2025-03-19更新）

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
