# RUN-DATA-05: データ遅延インシデント対応手順

> **ACカバレッジ**: AC-04, AC-45  
> **Runbook版数**: v1.5
> **最終更新日**: 2025-03-22
> **最終更新者**: Ops Manager / Codex Liaison

## 目的
- `HealthMonitor`が`data_latency`アラートを発火した際に、サービス停止を最小化しつつ代替ソースへ切り替え、SLA違反の根本原因を特定する。
- 復旧後に事後分析を`reports/performance/`へ反映し、再発防止タスクを明確化する。

## トリガー
- `fetch_delay_p95>18秒`または`processing_delay_p95>12秒`、もしくは`success_rate<99.0%`の警告が`tradectl status`/メールで通知されたとき。
- `fetch_delay_sec>60`もしくは連続3回以上の`fetch_timeout`で`critical(fetch)`アラートが発生したとき。
- SLA未達（`make sla-report`結果）や手動CSV投入の判断を要するレビュー時。

## 手順
1. `tradectl data health`で対象シンボルとプロバイダ、発生時刻、直近メトリクスを確認する。`metrics/data_ingestion_sla.jsonl`から前後30分のログを抽出し、`phase=fetch`/`phase=processing`それぞれの遅延を確認する。合わせて`config/sla_thresholds/active.yaml`（`schema_version`とRunbookリンクが`config/README.md`に記載されている雛形）を開き、`docs/schemas/sla_threshold_profile.schema.json`および`pytest -k config_schema_smoke`の検証結果が最新であることを確認した上で、現行プロファイルと閾値が一致しているかチェックする。
   - **Stage Eval記録**: `tradectl data status --provider <name> --log-stage-eval --json`を実行し、`metrics/rate_limit_window.jsonl`へ`stage_eval.stage|decision|sample_window_min|429_rate|tokens_remaining|approver_stub|runbook_ref`を含む手動記録を必ず追加する。出力JSONは`reports/validation_log/AC-45_sla_<date>.md`へ貼付し、`reports/implementation/20250315_pkg-data-status-01/cli/*.json`などのEvidenceディレクトリにも保存する。`--watch`はM1では未使用だが、同コマンドのJSON出力をOps Agendaへ共有することでTraderが判断をトレースできる。
   - **実装参照**: DataIngestionServiceの公開APIは`src/data/service.py`、各プロバイダスタブは`src/data/providers/`配下に集約。Manual CSV監査ログは`src/data/quality.py::DataQualityGuard.record_manual_csv_hash_verification`で`metrics/data_ingestion_manual.jsonl`（仮）へ出力するため、開発へのエスカレーション時は該当モジュールを参照する。
2. **Signal Boardガード制御**: `tradectl status --detail`の`board_guard`セクション（またはボードヘッダの警告バナー）で`board_mode=guarded`かつ`reduce_only=true`になっていることを確認し、以下のシーケンスをチェックリストに沿って記録する。
   - データ鮮度検証: `metrics/data_ingestion_sla.jsonl`/`metrics/pipeline_latency.jsonl`の逸脱区間を突き合わせ、復旧まで新規提案停止の根拠を`reports/validation_log/AC-45_sla_<date>.md`に追記する。
   - Reduce-Only運用: 既存ポジションの縮小提案のみがSignal Boardで許可されていることを確認し、対応チケットID・判断理由を`reports/audit/reduce_only/<date>.md`へ記録する。
   - 復旧確認: Runbook `docs/runbooks/RUN-DATA-06.md`の補完状況とCatch-upログを参照し、`catch_up_lag_minutes<30`になるまで新規提案が再開されないようにする。
   - 提案再開: 上記3項目が完了した後にのみ解除判定に進むこと、`degraded_ack`イベントはこのステップの完了時に1回だけ発行することを明記する。
   - Signal cycle snapshot: `tradectl board --view strategy --save-snapshot reports/validation_log/evidence/<date>/board_snapshot.json` を取得し、`docs/templates/validation_log.md`および`reports/validation_log/templates/playbook_entry.md`の`signal_cycle_snapshot`欄を更新する。
   - CLI確認ログ: `tradectl status --json` で `ops.banner.kind="acceptable_degradation"`、`ops.banner.runbook="docs/runbooks/RUN-DATA-05.md"`、`ops.actions.ack.status="queued"` であることを保存する。以下のような出力をOps Evidenceに貼付する。

     ```console
     $ tradectl status --json
     {
       "ops": {
         "banner": {
           "kind": "acceptable_degradation",
           "reduce_only": true,
           "runbook": "docs/runbooks/RUN-DATA-05.md"
         },
         "actions": {
           "ack": {"status": "queued"},
           "kill_switch": {"status": "idle"}
         }
       },
       "snapshots": {"status": "unavailable", "base_path": "snapshots"}
     }
     ```
3. `tradectl data switch --to <provider>`または`tradectl data failover --to cache`で代替ソースへ切り替え、`FallbackRetryTask`のステータスを`tradectl data jobs --pending`で確認する。結果を`reports/audit/rates/<date>.md`に追記し、`reports/validation_log/AC-45_sla_<date>.md`へリンクを残す。
4. フォールバック後も欠損が続く場合は`tradectl data jobs enqueue --task manual_csv --symbol <symbol>`を準備し、必要な双子CSVを`data/manual_fallback/<provider>/<symbol>/<YYYYMMDD>/fallback_<provider>_<symbol>_<tf>_<YYYYMMDD>_{op,review}.csv`として配置する。手動モード移行時はRunbook `docs/runbooks/RUN-DATA-06.md`のチェックリストも参照する。
5. 原因分析としてネットワーク状態・APIレスポンス・利用規約制約を確認し、`reports/audit/license/`および`reports/quality/<date>.md`に記録する。処理遅延が原因の場合は`ProviderParseWorker`/`DataQualityGuard`のログを添付する。
6. 復旧を確認したらチェックリストの完了と新規提案再開条件をダブルサインし、`tradectl data ack --provider <name>`で承認した上で`HealthMonitor.ack`を実行する。`degraded_ack`監査イベントのIDと再開時刻を`reports/validation_log/AC-45_sla_<date>.md`へ追記し、事後分析と改善策は24時間以内に`reports/performance/<mode>/<date>.md`へ反映する。

## プロファイル別チューニング手順（§11.1 リスク#4対応）
- **目的**: macOSローカル運用でネットワーク品質が不安定な場合でもCatch-up時間を抑えるため、`provider.timeout`/`retry`とバックフィル分割手順を明文化する。
- **Config更新**:
  1. `config/provider_profiles/local.yaml`を開き、`timeout_sec`/`retry.max_attempts`/`retry.backoff_sec`を見直す。推奨値: timeout=8→12、max_attempts=3→5、backoff=2秒ごと（Ops判断）。
  2. `poetry run schema-validate config/provider_profiles/local.yaml --schema docs/schemas/provider_profile.schema.json`で検証し、`reports/risk/20250318_prelaunch/data_latency_tuning.md`へDiffとハッシュを貼る。
- **バックフィル分割**:
  - 長時間停止後のCatch-upは`tradectl resync --since <ISO8601> --chunk 6h --pause 30s`で6時間単位に分割する。`--chunk`はM1 CLIのオプション（存在しない場合は手動で期間を分割）としてログに記録し、1チャンクごとに`metrics/resync/chunks.jsonl`へ`catch_up_lag_minutes`を追記する。
  - `reports/resync/chunk_plan_<date>.md`（新規）にチャンク数・所要時間・失敗箇所を書き出し、`reports/validation_log/AC-04_<date>.md`へリンクする。
- **SLA再調整**:
  - `python tools/sla/generate_profile.py --input metrics/data_ingestion_sla.jsonl --profile local --out config/sla_thresholds/candidate_local_latency.yaml`で新候補を生成し、`tradectl sla profile apply --file config/sla_thresholds/candidate_local_latency.yaml`（M1 CLIスタブ）を実行する。
  - 適用結果を`reports/risk/20250318_prelaunch/data_latency_tuning.md`へサマリし、Opsレビューで承認を得る。
- **Ops Agenda統合**: `tradectl ops agenda --date <YYYY-MM-DD> --include-latency-review`（スタブ）で`data_latency_review`タスクを挿入し、完了時に`ops_worklog`へ`{"task":"data_latency_review","status":"done"}`を記録する。
- **Evidence**: `reports/risk/20250318_prelaunch/data_latency_tuning.md`と`reports/validation_log/AC-45_sla_<date>.md`。


## 責任者
- オペレーションズマネージャ（初動と調整の指揮）
- プロダクトオーナー（Kill Switch解除と再開判断）
- データ取得担当/開発者（技術検証と修正作業）
