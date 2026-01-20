# RUN-SHADOW-02: Shadow GUI起動・検証手順

> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-18  
> **最終更新者**: Ops Manager (Doc Maintainer)

> **参照**: [詳細設計 §60.2 ShadowSessionOrchestrator & GUI Feed](../../detailed_design_fx_signal_tool_v1.md#602-shadowsessionorchestrator--gui-feed-srcshadowsessionpy-srcinterfacesguishadow_apipy)
> **関連コマンド**: `tradectl shadow serve`, `tradectl shadow status`

## 目的
- Shadow GUI APIの疎通とトークン設定を検証する。
- CLI/Shadow StateからGUIへのフィードが流れる前提を確認する。

## トリガー
- Shadow GUI PoCの起動前。
- Shadowチャンネル/イベントストリームの不整合が疑われたとき。

## 事前準備
1. `config/shadow/tokens.yaml`にGUIトークンを設定する。
2. `data/shadow_state.db`が生成済みであることを確認する。

## 手順
1. `tradectl shadow serve --dry-run --port 7777`を実行し、
   `token_count`と`schema_path`が表示されることを確認する。
2. `tradectl shadow status`で`ShadowStateStore`にチケット/アラート/ACKが入っていることを確認。
3. GUI側は`docs/schema/shadow_gui.yaml`の契約に合わせてエンドポイントを接続する。

## 証跡
- `metrics/shadow_gui.jsonl`
- `logs/audit/shadow_gui.jsonl`
- `logs/events/shadow_session.jsonl`

## 注意事項
- `tradectl shadow serve`はPoC用のスタブであり、M2以降で本番サーバ実装へ移行する。
