# RUN-SHADOW-GW-02: Shadow Gatewayキャッシュリプレイドリル

> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-24  
> **最終更新者**: Ops Manager (Doc Maintainer)  
> **参照**: 詳細設計 §87.2 Shadow Gateway Runbook運用  
> **関連コマンド**: `make load-shadow-gateway`, `make chaos-shadow-gateway`

## 目的
- Offline Cacheのリプレイとキャッシュ証跡を確認する。
- バックプレッシャ時の挙動と再送成功率を検証する。

## トリガー
- Shadow Gatewayのオフラインキャッシュ導入時。
- キャッシュリプレイ失敗が報告されたとき。

## 手順
1. **キャッシュリプレイ負荷テスト**
   - `make load-shadow-gateway ARGS="--duration 10m"` を実行する。
2. **レポート確認**
   - `reports/ops/shadow_gateway/cache_replay.md` の `batch_size` と `checksum` を確認。
3. **メトリクス/監査確認**
   - `metrics/shadow_gateway.jsonl` に `shadow.gateway.cache_replay_success` が記録されていることを確認。
   - `logs/audit/shadow_gateway.jsonl` に `audit.shadow_gateway.cache` が記録されていることを確認。
4. **Validation Playbook登録**
   - `validation_playbook/FR47_shadow_gateway.yaml` に証跡を記録する。

## 証跡
- `metrics/shadow_gateway.jsonl`
- `logs/audit/shadow_gateway.jsonl`
- `reports/ops/shadow_gateway/cache_replay.md`
- `reports/validation_log/shadow_gateway_chaos_<date>.md`

## 注意事項
- キャッシュリプレイ失敗時は `RUN-SHADOW-GW-01` のフェイルオーバー手順へ遷移する。
