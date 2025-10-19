# RUN-DATA-05: データ遅延インシデント対応手順

> **ACカバレッジ**: AC-04, AC-45  
> **Runbook版数**: v1.1  
> **最終更新日**: 2025-03-08  
> **最終更新者**: Ops Manager (Doc Maintainer)

## 目的
- `HealthMonitor`が`data_latency`アラートを発火した際に、サービス停止を最小化しつつ代替ソースへ切り替え、SLA違反の根本原因を特定する。
- 復旧後に事後分析を`reports/performance/`へ反映し、再発防止タスクを明確化する。

## トリガー
- `fetch_delay_p95>18秒`または`processing_delay_p95>12秒`、もしくは`success_rate<99.0%`の警告が`tradectl status`/メールで通知されたとき。
- `fetch_delay_sec>60`もしくは連続3回以上の`fetch_timeout`で`critical(fetch)`アラートが発生したとき。
- SLA未達（`make sla-report`結果）や手動CSV投入の判断を要するレビュー時。

## 手順
1. `tradectl data health`で対象シンボルとプロバイダ、発生時刻、直近メトリクスを確認する。`metrics/data_ingestion_sla.jsonl`から前後30分のログを抽出し、`phase=fetch`/`phase=processing`それぞれの遅延を確認する。
2. `tradectl data switch --to <provider>`または`tradectl data failover --to cache`で代替ソースへ切り替え、`FallbackRetryTask`のステータスを`tradectl data jobs --pending`で確認する。結果を`reports/audit/rates/<date>.md`に追記し、`reports/validation_log/AC-45_sla_<date>.md`へリンクを残す。
3. フォールバック後も欠損が続く場合は`tradectl data jobs enqueue --task manual_csv --symbol <symbol>`を準備し、必要なCSVを`data/manual/<date>/`に配置する。手動モード移行時はRunbook `docs/runbooks/RUN-DATA-06.md`のチェックリストも参照する。
4. 原因分析としてネットワーク状態・APIレスポンス・利用規約制約を確認し、`reports/audit/license/`および`reports/quality/<date>.md`に記録する。処理遅延が原因の場合は`ProviderParseWorker`/`DataQualityGuard`のログを添付する。
5. 復旧を確認したら`tradectl data ack --provider <name>`で承認し、`HealthMonitor.ack`を実行してKill Switchを解除する。事後分析と改善策は24時間以内に`reports/performance/<mode>/<date>.md`と`reports/validation_log/AC-45_sla_<date>.md`へ追記する。

## 責任者
- オペレーションズマネージャ（初動と調整の指揮）
- プロダクトオーナー（Kill Switch解除と再開判断）
- データ取得担当/開発者（技術検証と修正作業）
