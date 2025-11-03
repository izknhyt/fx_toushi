# RUN-EXEC-02: Executionモデル再キャリブレーション手順

> **ACカバレッジ**: AC-34, AC-43  
> **Runbook版数**: v1.0  
> **最終更新日**: 2025-03-23  
> **最終更新者**: Quant Lead (Execution Desk)

## 目的
- `ExecutionModel`の遅延・スリッページ分布がライブ fills と乖離した際に、最小限のボード停止で新パラメータへ更新する。
- `execution.latency_alert`発火時のKill Switch判定、Reduce-Only運用、再開条件を標準化する。
- 再キャリブレーションに用いたデータセット・CLIログ・検証結果を`reports/validation_log/`へ一元管理し、監査トレースを確保する。

## トリガー
- `HealthMonitor`が`execution_latency_drift`を理由に`degraded`を発火したとき（自動またはOps判断）。
- 週次レビューで`metrics/performance_live_guard.jsonl`の`latency_p75`が`config.risk.live_guard.latency_p75_threshold`を超えたとき。
- `RUN-RISK-07`のライブ性能ガード手順でReduce-Onlyが継続し、POが再開判断のために最新分布を要求したとき。

## 手順
1. **初動確認**
   - `tradectl status --verbose`で`board_mode`と`recommended_action`を確認し、`execution_latency_drift`が原因であることを特定する。
   - `tradectl kill-switch review --reason execution_latency --strategy <strategy_id>`を実行し、`reports/audit/kill_switch_review/<timestamp>.md`へ証跡を生成する。
   - `RUN-RISK-07`と合わせてReduce-Only運用へ移行し、Opsに`logs/ops/workload.log`への記録を依頼する。
2. **データセット検証**
   - `ls -lh reports/performance/live_fill_stats.parquet`で最新更新日時を確認。7日以上更新されていない場合はデータ取得ワークフローを優先修復する。
   - `tradectl performance live-guard --strategy <strategy_id> --output json --strict`の結果を`reports/weekly/evidence/<YYYY-WW>/live_guard.json`として保存し、閾値逸脱項目をRunbook `RUN-RISK-07`と突合する。
3. **再キャリブレーション実行**
   - 次のCLIを実行し、`config/execution_model.calib.yaml`を生成する。`--window`はデフォルト30日、必要に応じて調整する。

     ```console
     $ tradectl execution recalibrate \
         --from reports/performance/live_fill_stats.parquet \
         --window 30d \
         --out config/execution_model.calib.yaml \
         --strict
     Loading fills: 12,418 rows (window=30d, mode=live)
     Writing calibrated profiles -> config/execution_model.calib.yaml
     p95 latency exceeded threshold for EURUSD/high_volatility (212ms > 180ms)
     EXIT 0 (strict mode)
     ```
   - `--strict`でExit code 44となった場合は、`reports/validation_log/execution_recalibration_<date>.md`へエラー内容を貼り付け、Ops/POへ減速策（Reduce-Only継続、サイズ制限）を提示する。
4. **検証**
   - `poetry run schema-validate config/execution_model.calib.yaml --schema docs/schemas/execution_model.schema.json`
   - `poetry run exec-model validate --config config/execution_model.calib.yaml`
   - `pytest -k execution_model`（未整備の場合は`tests/unit/test_live_performance_guard.py`の関連ケースを参照し、後続Packetで追加する）
   - 検証ログを`reports/validation_log/execution_recalibration_<date>.md`へ添付し、CI実行結果と整合することを確認。
5. **適用と差分確認**
   - `cp config/execution_model.calib.yaml config/execution_model.yaml`（`git diff`で差分レビューが済んでいることを確認してから上書き）。
   - `poetry run schema-validate config --schema docs/schemas/config_bundle.schema.json`
   - `pytest -k config_schema_smoke and execution_model`を再実行して全体整合を確認。
   - `git diff config/execution_model.yaml`を`reports/validation_log/execution_recalibration_<date>.md`の`Diff`節へ貼り付ける。
6. **サインオフ**
   - Quant LeadとOps Managerが`reports/validation_log/execution_recalibration_<date>.md`にイニシャルを追記し、`docs/review_log.md`の`EXEC-{{date}}`エントリへリンクする。
   - POが`docs/runbooks/RUN-EXEC-02.md`の最新版を確認し、`tradectl status --json`の`execution.latency_alert`が`resolved`に変化したことを`logs/health/events.jsonl`で確認する。
   - Reduce-Only解除は`RUN-RISK-07`の回復条件（PF/Sharpe/Latency閾値が連続2日以内）を満たした後、`tradectl board --normal`→`health.ack --reason execution_latency_recovered`の順に実行する。

## 証跡と保存先
- `reports/validation_log/execution_recalibration_<date>.md`（Dry Run, CLIログ, 検証結果, Diff, サイン）
- `reports/weekly/evidence/<YYYY-WW>/live_guard.json`（Live Guard確認）
- `reports/audit/kill_switch_review/<timestamp>.md`（Reduce-Only/停止判断の根拠）
- `metrics/execution_recalibration.jsonl`（CLIが自動追記、週次Opsレビューでトレンド監視）

## 責任者
- **一次担当**: Quant Lead（Execution担当）
- **レビュー**: Risk Manager（閾値妥当性）, Ops Manager（運用手順整合）
- **エスカレーション先**: RUN-RISK-07（ライブ性能ガード継続が必要な場合）, RUN-HITL-01（手動エントリへ切替が必要な場合）
