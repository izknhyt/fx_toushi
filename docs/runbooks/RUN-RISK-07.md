# RUN-RISK-07: ライブ性能ガード（PF/Sharpe/Latency）対応手順

> **ACカバレッジ**: AC-34, AC-45, AC-52  
> **Runbook版数**: v1.1  
> **最終更新日**: 2026-01-12  
> **最終更新者**: Codex (Doc Maintainer)

## 目的
- `tradectl performance live-guard`で検知されるPF/Sharpe/Latency逸脱に対し、速やかにReduce-Onlyモードへ遷移し、Kill Switch判定と戦略調整を実施する。
- リスク閾値（`config/risk_live_guard.yaml`）と実績メトリクスの差分を明文化し、Ops/Quant/PO間の合意形成を迅速化する。
- 対応過程で生成するCLIログ・証跡ファイルを`reports/validation_log/`へ集約し、週次レビューと監査で再利用できる形に整える。

## トリガー
- `tradectl performance live-guard --strategy <id> --strict`がExit code 42または`status=alert`を返したとき。
- `HealthMonitor`が`performance_live_guard_breach`で`degraded`を発火、または`ExecutionModel`側から`execution.latency_alert`と共にReduce-Only推奨が提示されたとき。
- 週次レポート作成時に`metrics/performance_live_guard.jsonl`の`pf_trailing`/`sharpe_trailing`/`latency_p75`が閾値を下回っていると判明したとき。

## 手順
1. **検知と初期アセスメント**
   - `tradectl performance live-guard --strategy <id> --output json --window 4w --strict`を実行し、出力を`reports/weekly/evidence/<YYYY-WW>/live_guard.json`へ保存する。

     ```console
     $ tradectl performance live-guard --strategy m1_baseline --window 4w --mode live --output md --strict
     PF_trailing: 0.94 (threshold 1.08)  -> ALERT
     Sharpe_trailing: 0.82 (threshold 0.90) -> WARN
     latency_p75: 138ms (threshold 120ms) -> ALERT
     recommended_mode: guarded
     runbook: docs/runbooks/RUN-RISK-07.md#stabilise
     EXIT 42
     ```
   - `metrics/performance_live_guard.jsonl`の最新10件を確認し、逸脱が一時的か継続的かを判断する。
   - `tradectl status --verbose`で`board_mode`, `reduce_only`, `recommended_action`を確認する。
2. **Stabilise: Reduce-OnlyとKill Switch準備**
   - `tradectl board --guarded --reason live_guard_breach`を実行し、BoardをReduce-Onlyへ変更する。
   - `tradectl kill-switch review --reason live_guard --strategy <id>`を実行して`reports/audit/kill_switch_review/<timestamp>.md`を生成する。
   - `logs/ops/workload.log`へ対応開始時刻と担当者を記録する（CLI `tradectl ops workload log --task live_performance_review --strategy <id>`を使用予定）。
   - `RUN-DATA-05`/`RUN-DATA-06`と突合し、データ遅延・Spread異常が同時発生していないか確認する。
3. **根本原因分析**
   - **Executionモデル**: `RUN-EXEC-02`を参照し、`tradectl execution recalibrate --from reports/performance/live_fill_stats.parquet`の必要性を評価する。
   - **Strategyパラメータ**: `config/strategy_manifest.yaml`の`weight`, `enabled`, `risk_tags`を見直し、必要に応じて`make config-init --dry-run`でテンプレ差分を確認する。
   - **Market要因**: `reports/ops/degradation_log/<YYYYMMDD>.md`と`metrics/spread_cooldown.jsonl`を突合し、市場構造変化によるPF悪化かを判定する。
4. **是正アクション**
   - `tradectl performance live-guard --strategy <id> --output md --save reports/weekly/evidence/<YYYY-WW>/live_guard.md`で人間向けサマリを生成し、改善タスクを列挙する。
   - 例: ポジション縮小は`config/risk_policy.yaml::position_limits`, 手動介入は`RUN-HITL-01`, データ補完は`RUN-DATA-05`参照。
   - Opsが実施した手動アクションは`docs/development_plan.md#update-log-utc`（カテゴリ: `LG-<YYYYWW>`）と`ops_worklog`に記録する。
5. **モニタリングと解除判定**
   - 翌営業日から`tradectl performance live-guard --strategy <id> --strict --output json`を毎日実行し、`metrics/performance_live_guard.jsonl`に追記される`pf_trailing`/`sharpe_trailing`/`latency_p75`を監視する。
   - 解除条件: `pf_trailing ≥ config.risk.live_guard.pf_threshold`かつ`latency_p75 ≤ config.risk.live_guard.latency_p75_threshold`が連続2日以上、`P&L drawdown`が`config/risk_policy.yaml`の`weekly_drawdown_pct`以内。
   - 条件達成後に`tradectl board --normal`→`health.ack --reason live_guard_recovered`を実行し、`logs/health/events.jsonl`へ記録されたIDを`reports/validation_log/live_guard_recovery_<date>.md`へ転記する。
6. **事後レビュー**
   - `reports/validation_log/live_guard_<date>.md`を作成し、以下を含める。
     - トリガーとなったCLI出力（Markdown/JSON）
     - 実施アクションと実装箇所（例: `src/risk/live_guard.py`）
     - `RUN-EXEC-02`または他Runbookへのエスカレーション有無
     - 再発防止タスク（`tickets/live_guard_followup/<date>.md`）
   - 週次OpsレビューでPO/Risk Managerがサインし、`docs/development_plan.md#update-log-utc`の該当週へリンクを追加する。

## Board/Weeklyレポート統合（§11.1 リスク#5対応）
- **Board Modeの強制**: `LATENCY-LIVE-GUARD`が連続Failした場合、`tradectl board --guarded`でBoardMode=guardedを強制し、`reports/audit/kill_switch_review/<timestamp>.md`に`reason=live_guard_chain_fail`を追記する。解除条件は本RunbookのStep5に従い、2営業日連続でPF/Latencyが閾値内に戻るまで維持する。
- **Ops Agenda連携**: `tradectl ops agenda --date <YYYY-MM-DD> --include live_guard`（スタブ）で`live_guard_board_review`タスクを生成し、Ops Managerが`ops_worklog`へ`{"task":"live_guard_board_review","status":"queued"}`→`:"done"`を記録する。
- **レポート整合**: `tradectl report weekly --since 7d --section live_guard`の出力を`reports/weekly/evidence/<YYYY-WW>/live_guard_board.md`へ貼り付け、`OPS-74`チェックリストに「Board/Weekly PF整合」項目としてリンクする。
- **Evidence**: `reports/risk/20250318_prelaunch/live_guard_board_mode.md`（Boardスナップショット、Ops/POサイン付き）。
- **Closed条件**: 上記エビデンスが最新週まで揃い、`docs/development_plan.md#update-log-utc`へ「Closed (RUN-RISK-07 v1.0 board addendum)」を追記する。

## 証跡と保存先
- `reports/weekly/evidence/<YYYY-WW>/live_guard.{json,md}`
- `reports/validation_log/live_guard_<date>.md`（初動〜解除までの全ログ）
- `reports/audit/kill_switch_review/<timestamp>.md`
- `metrics/performance_live_guard.jsonl`（CLIが自動追記）
- `logs/ops/workload.log`, `docs/development_plan.md#update-log-utc`（カテゴリ: `LG-<YYYYWW>`）

## 関連Runbook/依存
- `RUN-EXEC-02`: Execution再キャリブレーション
- `RUN-DATA-05` / `RUN-DATA-06`: データ遅延・Catch-up対応
- `OPS-READINESS-01`: Opsレディネスの再評価と解除判断
- `CONFIG-SCAFF-01`: `risk_live_guard.yaml`更新時のテンプレ整合

## 責任者
- **一次担当**: Risk Manager
- **レビュー**: Quant Lead（PF/Sharpe再評価）, Ops Manager（Reduce-Only運用）
- **エスカレーション先**: Product Owner（Kill Switch最終判断）、Trader Lead（ポジション調整）
