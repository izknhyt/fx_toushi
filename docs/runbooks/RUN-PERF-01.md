# RUN-PERF-01: パイプライン性能モニタリング手順

> **ACカバレッジ**: AC-05, AC-45（性能指標）
> **Runbook版数**: v0.1
> **最終更新日**: 2025-03-10
> **最終更新者**: Ops Manager (Doc Maintainer)

## 目的
- `metrics/pipeline_latency.jsonl`および関連メトリクスを監視し、データパイプラインとボード表示の性能退行を早期に検出する。
- SLA逸脱時の是正措置と証跡記録を統一し、監査時に再現できるようにする。
- グラフやスパークラインを更新し、関係者が直近の性能トレンドを迅速に把握できるようにする。

## 適用範囲・トリガー
- `pytest tests/perf/test_pipeline_latency.py`が失敗したとき。
- 週次Opsレビュー、月次SLAレビュー、AC-45四半期サインオフの際。
- `HealthMonitor`や`metrics_watchdog`が性能閾値（p95>90秒等）を検知したとき。

## 事前準備
- `metrics/pipeline_latency.jsonl`と`metrics/data_ingestion_sla.jsonl`が最新であることを確認。
- `tools/render_perf_chart.py`が実行可能（必要なPython依存関係がインストール）であることを確認。
- `reports/validation_log/AC-45_sla_<date>.md`のテンプレートを用意し、前回レビュー内容を参照。
- Ops ManagerとData Engineerがレビューに参加できるようスケジュール調整。

## 手順
1. `pytest tests/perf/test_pipeline_latency.py -k test_pipeline_latency_thresholds --maxfail=1`を実行し、直近500サンプルのp95/p99が閾値内か確認。
2. `python tools/render_perf_chart.py --input metrics/pipeline_latency.jsonl --output reports/performance/pipeline_latency_<date>.svg`でスパークラインを生成し、Runbookチケットに添付。
3. `tradectl metrics report --kind latency --window 7d --out reports/performance/pipeline_latency_<date>.md`を実行し、指標の要約をMarkdown化。
4. Ops Managerが`tickets/runbooks/RUN-PERF-01/<date>.md`を作成し、以下を記録:
   - 実行日時と担当者
   - p95/p99値と閾値
   - 失敗テスト（ある場合）
   - 対応アクション（キャッシュクリア、リトライ設定変更等）
5. SLA逸脱があった場合は`reports/audit/perf_incidents/<date>.md`を作成し、根本原因・是正計画・影響範囲を記載。`docs/runbooks/RUN-DATA-05.md`のエスカレーション手順を参照。
6. `reports/validation_log/AC-45_sla_<date>.md`へ結果を追記し、レビュー参加者のサインを残す。

## チェックリスト
- [ ] `pytest tests/perf/test_pipeline_latency.py`の実行結果確認
- [ ] スパークラインPNGの更新と保存
- [ ] `tradectl metrics report`のMarkdown出力保存
- [ ] Runbookチケットへの記録とサイン
- [ ] SLA逸脱時のインシデントログ作成
- [ ] `reports/validation_log/AC-45_sla_<date>.md`への記録

## エスカレーション
- p99>120秒が2回連続した場合は`HealthMonitor.raise('critical','pipeline_latency')`を発火し、`docs/runbooks/OPS-READINESS-01.md`の緊急対応に移行。
- SLA逸脱が解消しない場合はData Engineerが`pipelines/config.yaml`の再デプロイまたはリトライ設定調整を実施し、結果をRunbookチケットへ追記。
- 手動フェイルオーバーが必要な場合は`docs/runbooks/RUN-DATA-06.md`のプロバイダ切替手順を参照。

## 履歴更新手順
- Runbook更新時は版数と最終更新日を変更し、`reports/governance/runbook_changelog.md`に差分を記録する。
- Validation Data Playbook（要件定義§8.2, AC-45行）および関連設計文書のRunbook欄/版数欄を更新する。
