# RUN-DATA-05: データ遅延インシデント対応手順

> **ACカバレッジ**: AC-04, AC-45  
> **Runbook版数**: v1.2
> **最終更新日**: 2025-03-09
> **最終更新者**: Ops Manager (Doc Maintainer)

## 目的
- `HealthMonitor`が`data_latency`アラートを発火した際に、サービス停止を最小化しつつ代替ソースへ切り替え、SLA違反の根本原因を特定する。
- 復旧後に事後分析を`reports/performance/`へ反映し、再発防止タスクを明確化する。

## トリガー
- `fetch_delay_p95>18秒`または`processing_delay_p95>12秒`、もしくは`success_rate<99.0%`の警告が`tradectl status`/メールで通知されたとき。
- `fetch_delay_sec>60`もしくは連続3回以上の`fetch_timeout`で`critical(fetch)`アラートが発生したとき。
- SLA未達（`make sla-report`結果）や手動CSV投入の判断を要するレビュー時。

## 手順
1. `tradectl data health`で対象シンボルとプロバイダ、発生時刻、直近メトリクスを確認する。`metrics/data_ingestion_sla.jsonl`から前後30分のログを抽出し、`phase=fetch`/`phase=processing`それぞれの遅延を確認する。合わせて`config/sla_thresholds/active.yaml`（`schema_version`とRunbookリンクが`config/README.md`に記載されている雛形）を開き、`docs/schemas/sla_threshold_profile.schema.json`および`pytest -k config_schema_smoke`の検証結果が最新であることを確認した上で、現行プロファイルと閾値が一致しているかチェックする。
   - **実装参照**: DataIngestionServiceの公開APIは`src/data/service.py`、各プロバイダスタブは`src/data/providers/`配下に集約。Manual CSV監査ログは`src/data/quality.py::DataQualityGuard.record_manual_csv_hash_verification`で`metrics/data_ingestion_manual.jsonl`（仮）へ出力するため、開発へのエスカレーション時は該当モジュールを参照する。
2. **Signal Boardガード制御**: `tradectl status --detail`の`board_guard`セクション（またはボードヘッダの警告バナー）で`board_mode=guarded`かつ`reduce_only=true`になっていることを確認し、以下のシーケンスをチェックリストに沿って記録する。
   - データ鮮度検証: `metrics/data_ingestion_sla.jsonl`/`metrics/pipeline_latency.jsonl`の逸脱区間を突き合わせ、復旧まで新規提案停止の根拠を`reports/validation_log/AC-45_sla_<date>.md`に追記する。
   - Reduce-Only運用: 既存ポジションの縮小提案のみがSignal Boardで許可されていることを確認し、対応チケットID・判断理由を`reports/audit/reduce_only/<date>.md`へ記録する。
   - 復旧確認: Runbook `docs/runbooks/RUN-DATA-06.md`の補完状況とCatch-upログを参照し、`catch_up_lag_minutes<30`になるまで新規提案が再開されないようにする。
   - 提案再開: 上記3項目が完了した後にのみ解除判定に進むこと、`degraded_ack`イベントはこのステップの完了時に1回だけ発行することを明記する。
3. `tradectl data switch --to <provider>`または`tradectl data failover --to cache`で代替ソースへ切り替え、`FallbackRetryTask`のステータスを`tradectl data jobs --pending`で確認する。結果を`reports/audit/rates/<date>.md`に追記し、`reports/validation_log/AC-45_sla_<date>.md`へリンクを残す。
4. フォールバック後も欠損が続く場合は`tradectl data jobs enqueue --task manual_csv --symbol <symbol>`を準備し、必要な双子CSVを`data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/fallback_<provider>_<symbol>_<tf>_<YYYYMMDD>_{op,review}.csv`として配置する。手動モード移行時はRunbook `docs/runbooks/RUN-DATA-06.md`のチェックリストも参照する。
5. 原因分析としてネットワーク状態・APIレスポンス・利用規約制約を確認し、`reports/audit/license/`および`reports/quality/<date>.md`に記録する。処理遅延が原因の場合は`ProviderParseWorker`/`DataQualityGuard`のログを添付する。
6. 復旧を確認したらチェックリストの完了と新規提案再開条件をダブルサインし、`tradectl data ack --provider <name>`で承認した上で`HealthMonitor.ack`を実行する。`degraded_ack`監査イベントのIDと再開時刻を`reports/validation_log/AC-45_sla_<date>.md`へ追記し、事後分析と改善策は24時間以内に`reports/performance/<mode>/<date>.md`へ反映する。

## 責任者
- オペレーションズマネージャ（初動と調整の指揮）
- プロダクトオーナー（Kill Switch解除と再開判断）
- データ取得担当/開発者（技術検証と修正作業）
