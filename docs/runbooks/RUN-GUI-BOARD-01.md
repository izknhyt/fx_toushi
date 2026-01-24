# RUN-GUI-BOARD-01: GUI Board運用・Runbook更新対応

> **ACカバレッジ**: AC-10, AC-16, NFR-11, NFR-15  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-24  
> **最終更新者**: Ops Manager (Doc Maintainer)  
> **仕様参照**: detailed_design_fx_signal_tool_v1.md §86.2-§86.5  
> **運用シナリオID**: DRILL-gui_board_ops  
> **関連メトリクス/ログ**: metrics/gui_board.jsonl, logs/audit/gui_board.jsonl, reports/validation_log/AC-16_onboarding_<date>.md  
> **外部資料**: docs/runbooks/RUN-SHADOW-01.md, docs/runbooks/RUN-RISK-01.md, docs/runbooks/RUN-BROKER-API-03.md

## 目的
- GUI Board上の承認・却下・延期操作を監査し、運用証跡を残す。
- Runbook更新時にGUIが差分を通知し、Opsが確認したことを記録する。
- Telemetryを用いてGUI操作レイテンシとエラー率を監視する。

## トリガー
- GUI Boardに新しい操作フローを追加したとき。
- Runbook更新通知がGUIに表示されたとき。
- GUI操作のlatencyが閾値（800ms）を超過したとき。

## 手順
1. **GUI Telemetryの確認**
   - `metrics/gui_board.jsonl`で`latency_ms`と`shadow_roundtrip_ms`を確認する。
   - `latency_ms>800`が連続する場合は、`RUN-SHADOW-01`の回線確認を実施する。
2. **監査ログの確認**
   - `logs/audit/gui_board.jsonl`に`gui.ticket`/`gui.command`の記録があることを確認。
   - 監査ログに`ticket_id`と`action`が含まれることを確認。
3. **Runbook更新通知の確認**
   - GUIのDocsサイドバーで更新差分を確認し、`Acknowledge`を実行。
   - `reports/gui/runbook_ack.jsonl`に記録が残ることを確認。
4. **障害時対応**
   - GUI操作が失敗する場合は`RUN-RISK-01`と`RUN-BROKER-API-03`を参照。

## チェックリスト
- [ ] GUI telemetryに最新の操作記録がある
- [ ] GUI監査ログに`gui.ticket`/`gui.command`が記録されている
- [ ] Runbook更新のACKが`reports/gui/runbook_ack.jsonl`に記録された
- [ ] 異常時に関連Runbookへ誘導した

## 証跡
- `metrics/gui_board.jsonl`
- `logs/audit/gui_board.jsonl`
- `reports/gui/runbook_ack.jsonl`
