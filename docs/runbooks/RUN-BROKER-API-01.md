# RUN-BROKER-API-01: ブローカーAPI接続・サンドボックス検証

> **ACカバレッジ**: AC-03, AC-06, NFR-02, NFR-17  
> **Runbook版数**: v0.1  
> **最終更新日**: 2026-01-23  
> **最終更新者**: Ops Manager (Doc Maintainer)  
> **仕様参照**: detailed_design_fx_signal_tool_v1.md §79.1-§79.4  
> **運用シナリオID**: DRILL-broker_api_sandbox  
> **関連メトリクス/ログ**: metrics/broker_api.jsonl, logs/audit/broker_orders.jsonl, reports/validation_log/AC-06_broker_api_<date>.md  
> **外部資料**: config/feature_flags.yaml, config/broker_rules.yaml, docs/runbooks/RUN-BROKER-API-02.md, docs/runbooks/RUN-BROKER-API-03.md

## 目的
- Sandbox API接続と注文シミュレーションが正常に動作することを確認し、本番切替の前提を整える。
- Access GovernanceとKill Switchの拒否ロジックが注文経路に反映されていることを証跡化する。
- Broker APIの監査/メトリクスが更新されることを確認し、Ops Agendaに必要なフォローアップを残す。

## トリガー
- 新しいブローカーAPI連携を追加したとき。
- `brokers.api_enabled` を `true` へ昇格する前。
- 監査/セキュリティレビューの四半期点検時。

## 手順
1. **前提確認**
   - `config/feature_flags.yaml`で`brokers.api_enabled=false`かつ`brokers.api_sandbox_only=true`になっていることを確認。
   - `config/broker_rules.yaml`の対象シンボルが最新であることを確認。
   - Access Governanceで`principal_id`/`device_id`が有効登録済みであることを確認（`tradectl access principals list --json`）。
2. **Sandbox接続の準備**
   - `brokers.api_enabled`をSandbox検証用に`true`へ昇格する。
     ```console
     tradectl config flags --set brokers.api_enabled=true --profile paper
     tradectl config flags --set brokers.api_sandbox_only=true --profile paper
     ```
   - `BROKER_PRINCIPAL_ID`/`BROKER_DEVICE_ID`の環境変数、またはCLI引数でアクセス情報を設定。
3. **注文スモークの実行**
   - 以下を実行してサンドボックス注文がAckされることを確認:
     ```console
     make broker-api-smoke
     ```
   - `reports/validation_log/AC-06_broker_api_<date>.md`の生成を確認。
4. **監査・メトリクス確認**
   - `logs/audit/broker_orders.jsonl`に`audit.broker_order_submitted`/`audit.broker_order_ack`が記録されていることを確認。
   - `metrics/broker_api.jsonl`で`operation=order_router.submit`の記録があることを確認。
5. **例外時対応**
   - Access拒否/認証エラーは`RUN-BROKER-AUTH-01`を参照。
   - Rate Limit/Retryは`RUN-BROKER-API-02`を参照。
   - Compliance/契約問題は`RUN-BROKER-API-03`を参照。

## チェックリスト
- [ ] `brokers.api_enabled`をSandbox検証時のみ`true`に変更した
- [ ] `make broker-api-smoke`が成功し、Validation Logが生成された
- [ ] 監査ログとメトリクスに注文Ackが残っている
- [ ] `RUN-BROKER-API-02`/`RUN-BROKER-API-03`の参照パスを確認した

## 証跡
- `reports/validation_log/AC-06_broker_api_<date>.md`
- `logs/audit/broker_orders.jsonl`
- `metrics/broker_api.jsonl`
