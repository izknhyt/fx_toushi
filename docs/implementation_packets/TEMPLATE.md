# Implementation Packet: <EPxx-Py>

## メタデータ
- Epic: <EP-0x>
- Packet範囲: <機能概要>
- 参照セクション: <§x.x, §y.y>
- 依頼Issue/PR: <#123>（未割当の間は `docs/change_requests/<date>_packet_backlog.md` を指す）
- 作成日: <YYYY-MM-DD>
- 作成者: <Codex Liaison>
- エビデンス格納先: reports/implementation/<YYYYMMDD>_<packet_id>/

## 1. 目的と背景
- KPI/リスク影響:
- ユーザストーリー/Runbook整合:

## 2. 変更サマリ
| コンポーネント | 変更内容 | テスト指示 | Feature Flag |
| --- | --- | --- | --- |
| src/... | <内容> | `pytest -k ...` | <flag or N/A> |

## 3. チェックリスト
- [ ] 設計整合: 対象セクション引用・差分レビュー完了
- [ ] テスト実行: <command>
- [ ] 監査ログ検証: <手順>
- [ ] Rollback手順記載: docs/governance/feature_flag_register.md更新済み
- [ ] Trader Sign-offテンプレ発行: docs/trader_signoff/<EPxx-Py>.md

## 4. エビデンス
- CLI/スクリーンショット: docs/trader_signoff/<EPxx-Py>.md 参照
- メトリクス: reports/implementation/<...>/metrics/
- ログ: reports/implementation/<...>/logs/

## 5. リスクと依存関係
- 依存Packet:
- 懸念事項/Acceptable Degradationへの影響:

## 6. アクションアイテム
- Runbook更新ID:
- Follow-upチケット:

## 7. 更新履歴
| 日付 | 更新者 | 内容 |
| --- | --- | --- |
| 2025-02-21 | <name> | 初版作成 |
