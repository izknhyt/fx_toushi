# RUN-SHADOW-GW-01: Shadow Gatewayフェイルオーバードリル

> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-24  
> **最終更新者**: Ops Manager (Doc Maintainer)  
> **参照**: 詳細設計 §87.2 Shadow Gateway Runbook運用  
> **関連コマンド**: `tradectl shadow gateway status`, `tradectl shadow gateway failover`

## 目的
- Shadow Gatewayのフェイルオーバー切替と監査/メトリクス出力を確認する。
- `shadow.gateway.force_failover` トグルの影響を検証する。

## トリガー
- Shadow GatewayのPrimary接続が不安定になったとき。
- Shadow Gatewayのローンチ前演習。

## 手順
1. **事前チェック**
   - `tradectl shadow gateway status --profile paper` を実行し、`streaming=true` であることを確認する。
2. **フェイルオーバー実行**
   - `tradectl shadow gateway failover --profile paper` を実行する。
   - `shadow.gateway.force_failover=true` が記録されることを確認する。
3. **監査/メトリクス確認**
   - `logs/audit/shadow_gateway.jsonl` に `audit.shadow_gateway.session` が記録されることを確認。
   - `metrics/shadow_gateway.jsonl` に `shadow.gateway.reconnect_time` が記録されることを確認。
4. **復旧**
   - `tradectl shadow gateway failover --restore --profile paper` を実行する。

## 証跡
- `logs/audit/shadow_gateway.jsonl`
- `metrics/shadow_gateway.jsonl`
- `reports/validation_log/shadow_gateway_session_<date>.md`

## 注意事項
- 本手順は `validation_playbook/FR47_shadow_gateway.yaml` の証跡対象。
