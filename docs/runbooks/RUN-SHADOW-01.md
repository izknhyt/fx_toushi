# RUN-SHADOW-01: Shadow Slack通知・承認ログ手順

> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-18  
> **最終更新者**: Ops Manager (Doc Maintainer)

> **参照**: [詳細設計 §60 Signal Board Shadow & Notification Bridge](../../detailed_design_fx_signal_tool_v1.md#60-signal-board-shadow--notification-bridge設計fr-12-fr-47-m2準備)
> **関連コマンド**: `tradectl shadow test`, `tradectl shadow replay`, `tradectl shadow status`

## 目的
- Shadow Slackチャネルへの通知経路を検証し、HITL承認の状況を共有できる状態にする。
- `shadow.slack_enabled`の切替時に監査ログ/メトリクスが更新されることを確認する。

## トリガー
- Shadow Slack導入時の初回検証。
- 重要Runbook更新や緊急時の通知経路が必要になったとき。

## 事前準備
1. `config/feature_flags.yaml`で`shadow.slack_enabled=false`であることを確認。
2. `config/shadow/channels.yaml`にチャネルIDとRunbook参照を登録。
3. `config/shadow/tokens.yaml`にGUI/Shadow用のトークンを登録（必要な場合）。

## 手順
1. `tradectl shadow test --channel <channel_id> --ticket <ticket_json>`を実行し、
   `logs/shadow/slack_messages.jsonl`に`shadow.message.posted`が記録されることを確認。
2. `shadow.slack_enabled=true`へ切替後、通知がSlackチャンネルへ送信されることを確認。
3. Slack側のAck操作後、`logs/audit/shadow_interactions.jsonl`と`ops_worklog.jsonl`に記録が残ることを確認。
4. `tradectl shadow replay --since-hours 24`で再送が可能であることを確認。

## 証跡
- `logs/shadow/slack_messages.jsonl`
- `logs/audit/shadow_interactions.jsonl`
- `metrics/shadow_bridge.jsonl`
- `ops_worklog.jsonl`

## 注意事項
- Shadow Slack側では承認/却下は行わず、Ackのみを記録する。
- 重大アラートは`RUN-EMERGENCY-01`の指示に従う。
