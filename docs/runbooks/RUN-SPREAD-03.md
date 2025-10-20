# RUN-SPREAD-03: スプレッド監視とフェイルオーバー手順

> **ACカバレッジ**: AC-22, AC-45（スプレッド関連）
> **Runbook版数**: v0.1
> **最終更新日**: 2025-03-10
> **最終更新者**: Risk Manager (Doc Maintainer)

## 目的
- スプレッド監視の閾値逸脱やデータ欠損を検知した際に適切なフェイルオーバーと証跡記録を実施する。
- `spread_metrics.parquet`および`spread_provider_health.jsonl`の更新結果をレビューし、AC-22/AC-45の要件を満たす。
- Reduce-Only運用やKill Switch発火との連携を明確にし、Opsチームが迅速に対応できる状態を保つ。

## 適用範囲・トリガー
- `HealthMonitor`が`spread_latency`または`spread_anomaly`の`warning`/`critical`イベントを発火したとき。
- `tradectl spread report`でSLA閾値（p95>60秒、成功率<97.5%等）が逸脱したとき。
- プロバイダ切替や手動CSV投入を行う前後。

## 事前準備
- `data/spread_metrics.parquet`の最新スナップショットを取得し、ハッシュを控える。
- `spread_provider_health.jsonl`と`reports/performance/spread/<date>.md`の直近記録を確認。
- `docs/runbooks/RUN-RISK-01.md`と`docs/runbooks/OPS-READINESS-01.md`を参照できるよう準備。
- `tradectl spread` CLIへのアクセス権があることを確認。

## 手順
1. Ops Managerがアラートを受信したら`tradectl spread status --window 1h`を実行し、影響範囲と直近の閾値を確認。
2. `python tools/spread_diff.py --base data/spread_metrics.parquet --target data/spread_metrics_latest.parquet`で差分を算出し、結果を`reports/performance/spread/spread_diff_<date>.md`へ保存。
3. フェイルオーバーが必要な場合は`tradectl spread switch --to <provider>`を実行し、理由・時間帯・承認者を`reports/audit/spread/<date>.md`に記録。
4. Reduce-Onlyへ切り替える場合は`tradectl spread ack --provider <name> --mode reduce-only`を実行し、`docs/runbooks/RUN-RISK-01.md`に従ってKill Switch状態を監視。
5. 影響が解消したら`tradectl spread resume --provider <name>`で通常運用へ戻し、`HealthMonitor`のイベントが`resolved`になったことを確認。
6. `reports/validation_log/AC-22_<date>.md`および`reports/validation_log/AC-45_sla_<date>.md`に結果を追記し、担当者サインを残す。

## チェックリスト
- [ ] `tradectl spread status`の結果確認
- [ ] 差分レポート（`spread_diff_<date>.md`）の生成
- [ ] フェイルオーバー/Reduce-Only操作の記録
- [ ] アラート解除確認 (`HealthMonitor`が`resolved`)
- [ ] `reports/validation_log/AC-22_<date>.md`/`AC-45_sla_<date>.md`の更新
- [ ] Runbookチケットへのサイン

## エスカレーション
- `critical`アラートが30分以内に解消しない場合はRisk Managerへエスカレートし、`docs/runbooks/RUN-RISK-01.md`のKill Switch発火を検討。
- 手動CSVフェイルオーバーが必要な場合は`docs/runbooks/RUN-DATA-05.md`の手順でデータ品質を検証し、完了までReduce-Onlyを維持。
- プロバイダ障害が継続する場合は`OPS-READINESS-01`の緊急オーケストレーションを起動し、追加の連絡先・契約先への切替を調整。

## 履歴更新手順
- Runbook改訂時は版数・最終更新日・更新者を更新し、`reports/governance/runbook_changelog.md`へ履歴を追記。
- Validation Data Playbook（要件定義§8.2, AC-22/AC-45行）と関連設計文書のRunbook欄を更新する。
