# RUN-EMER-UNWIND-01: Kill Switch STOP ポジション・アンワインド手順

> **ACカバレッジ**: AC-03, AC-34, AC-43  
> **Runbook版数**: v1.0  
> **最終更新日**: 2025-03-20  
> **最終更新者**: Ops Manager (Doc Maintainer)  
> **SLA目標**: 自動アンワインド ≤8分 / 手動フォールバック ≤20分  
> **関連設計**: `detailed_design_fx_signal_tool_v1.md §19.3.3`  
> **関連CLI**: `tradectl emergency close-all`, `tradectl emergency cancel-open`, `tradectl emergency hedge`, `tradectl emergency status`, `tradectl kill-switch review`, `tradectl status`, `tradectl accounts status`  
> **イベントログ**: `logs/events/emergency.*.jsonl`, `logs/audit/kill_switch_*.jsonl`, `metrics/emergency_unwind.jsonl`, `ops_worklog.jsonl`

## 目的
- Kill Switchが`STOP`へ遷移した際に、残存ポジションと未約定注文を迅速かつ安全にゼロ化し、再エントリを防ぐ。
- 必要に応じてヘッジ口座へ残余エクスポージャを転送し、リスク指標（残存ノーショナル/NAV）が運用基準内に収束することを保証する。
- Runbook完了までKill Switch `STOP`状態を保持し、Ops/Risk/POのダブルサインを通過した後のみ`resume`審査へ進ませる。
- エビデンス（CLI出力/監査ログ/メトリクス）を`reports/ops`および`reports/audit`に集約し、監査対応時のトレーサビリティを担保する。

## 適用範囲・トリガー
- `KillSwitchState`が任意の状態から`STOP`へ遷移した時点（自動/手動問わず）。
- Emergency Orchestratorが`PB-POS-UNWIND`プレイブックを発火し、`tradectl emergency status`で進行中が確認された場合。
- リアルタイム運用中に減災が必要な重大インシデント（データ断絶・リスク制御逸脱・大規模スリッページ等）が発生した場合。

## 事前準備 / 前提条件
- Ops ManagerおよびRisk Managerが即時対応可能であること（連絡手段: Slack/電話）。
- `config/emergency.yaml`と`config/hedge_routes.yaml`が最新コミット、`pytest -k config_schema_smoke`が成功済み。
- `PositionManager`, `OrderLifecycleManager`, `HedgeExecutor`のCLIコマンド群が`tradectl emergency status --list`に表示され、Feature Flag `emergency.orchestrator_enabled=true`。
- `reports/ops/emergency_unwind_<date>.md`と`artifacts/emergency_unwind/`へ書き込み可能であること。
- ヘッジ口座/APIキーが有効で、`tradectl accounts status --with-positions --mode hedge`で正常応答が得られる。

## SLA / 承認マトリクス

| フロー | SLA目標 | 必須承認者 | 主要CLI / 入出力 | 証跡 / テレメトリ |
| --- | --- | --- | --- | --- |
| 自動アンワインド（Emergency Orchestrator経由） | Kill Switch `STOP`検知から平残完了まで≤8分<br>（検知≤30秒、`close-all`≤3分、`cancel-open`≤1分、ヘッジ≤3分、レビュー≤30秒） | Ops Manager + Risk Manager（ダブルアック）、POへ通知 | `tradectl emergency status --json`, `tradectl emergency close-all --commit --mode live`, `tradectl emergency cancel-open --commit`, `tradectl emergency hedge --commit --profile live-hedge`（JSON出力を`artifacts/emergency_unwind/<ts>/`へ保存） | `metrics/emergency_unwind.jsonl.auto_flatten_duration_sec`, `logs/audit/kill_switch_<date>.jsonl`, `reports/ops/emergency_unwind_<date>.md` |
| 手動フォールバック（自動失敗時） | 自動処理失敗を検知後≤20分で平残完了<br>（Close-All≤10分、ブローカー/ヘッジ≤8分、レビュー≤2分） | Ops Manager + Risk Manager + Trader On-call（執行確認）、POレビュー | `tradectl emergency close-all --dry-run`→`tradectl broker order submit --ticket <json>`またはブローカーUI→`tradectl accounts status --with-positions --mode live --json`, `tradectl emergency cancel-open --commit`, `tradectl kill-switch review --recommendation guarded` | `metrics/emergency_unwind.jsonl.manual_flatten_duration_sec`, `reports/audit/manual_unwind_<date>.md`, `evidence/broker/kill_switch/<incident_id>/`, `ops_worklog.jsonl` |

> **メモ**: `metrics/emergency_unwind.jsonl`に`auto_flatten_duration_sec`および`manual_flatten_duration_sec`が出力されたかどうかを`jq 'select(.event=="unwind_completed")'`で確認し、未記録の場合は`tradectl metrics flush --kind emergency_unwind`を実行してから証跡を採取する。

## 手順

### 1. Kill Switch 状態と初期インベントリ確認
1. `tradectl status --kill-switch --board`で`KillSwitch: STOP`と`BoardMode: halted`を確認。CLI出力を`artifacts/emergency_unwind/<ts>/status_before.json`へ保存。
2. `tradectl emergency status --export reports/ops/emergency_unwind_<date>.md`で`PB-POS-UNWIND`の状態を共有し、Ops/Risk双方が`tradectl emergency ack --playbook PB-POS-UNWIND --ack-user <id>`でダブルアックを実施。
3. `tradectl accounts status --with-positions --mode live --json > artifacts/emergency_unwind/<ts>/positions_before.json`を実行し、残存ノーショナル/証拠金情報を記録。NAV比をRunbookシートに記入。

### 2. ポジション強制クローズ（Close-All）
1. `tradectl emergency status --json | jq '.actions.close_all' > artifacts/emergency_unwind/<ts>/close_all_status_pre.json`で`execution_mode`と`state`を確認し、`auto_commit`か手動フォールバックかを判断する。
2. **自動モード (`execution_mode=="auto_commit"`)**: `tradectl emergency status --json`を30秒間隔で再取得し、`state`が`completed`に遷移したことと`result.positions_closed>0`を確認。3分を超えて`in_progress`のままの場合は`emergency.auto_commit_enabled=false`へ切替（DocOps: `config/feature_flags.yaml`更新→`tradectl emergency reload`）し、Runbookに「自動失敗」と記録して手動モードへ移行する。完了後、`tradectl emergency status --export reports/ops/emergency_unwind_<date>.md`を再実行して結果を追記する。
3. **手動フォールバック**: `tradectl emergency close-all --dry-run --mode live`で対象ポジション、概算`PnL`、証拠金インパクトを確認し、Ops/Risk/Trader On-callで実行可否を合意。Broker API経由での代替執行が必要な場合は`tradectl broker order submit --ticket artifacts/emergency_unwind/<ts>/close_all_plan.json`（`--dry-run`出力を保存）を利用し、約定後に`tradectl emergency close-all --commit --mode live`を再実行してRunbookチェックリストへ`positions_closed`/`residual_notional`を転記する。ブローカーUIを使用した場合はスクリーンショットを`evidence/broker/kill_switch/<incident_id>/`へ保存。
4. `metrics/emergency_unwind.jsonl`から`close_all_duration_sec`と`auto_flatten_duration_sec`または`manual_flatten_duration_sec`を抽出（例: `jq 'select(.event=="close_all_completed") | {duration_sec, auto_flatten_duration_sec, manual_flatten_duration_sec}' metrics/emergency_unwind.jsonl`）し、Runbookシートに貼付。閾値超過時は`RUN-OPS-AGENDA-01`へエスカレーションを記録する。
5. 残存ポジションが0にならない場合は、`tradectl emergency status --json`で未クローズ銘柄を確認し、追加の`close-all`アクションまたはブローカーサポートへの連絡を実施。再試行時は新しい`artifacts/emergency_unwind/<ts>/close_all_retry_<n>.json`を保存する。

### 3. 未約定注文のキャンセル（Cancel-Open）
1. `tradectl emergency status --json | jq '.actions.cancel_open' > artifacts/emergency_unwind/<ts>/cancel_open_status_pre.json`で自動/手動モードを確認。Reduce-Only提案・Shadow注文がある場合は`pending_linked=true`であることをチェック。
2. **自動モード**: `state`が`completed`へ遷移するまで1分間隔で監視し、`result.orders_cancelled`と`result.orders_skipped`をRunbookへ記録。1分を超えて`in_progress`のまま、または`failed`へ遷移した場合は`Emergency Orchestrator`ログ（`logs/events/emergency.cancel_open*.jsonl`）を確認し、手動モードへ切替えて再実行する。
3. **手動フォールバック**: `tradectl emergency cancel-open --dry-run --include-linked`で対象を確認後、Ops/Risk承認のもと`tradectl emergency cancel-open --commit`を実行。`orders_cancelled`/`orders_skipped`をRunbookに転記し、失敗した注文があれば`tradectl ops incident open --category order --severity high --summary "cancel-open failure"`でIncidentを起票。
4. `logs/events/order.lifecycle.jsonl`で`cancelled`イベントが全注文分記録されているかを確認し、`metrics/emergency_unwind.jsonl`の`orders_cancelled`をRunbookに記載する。

### 4. 残存エクスポージャ評価とヘッジ
1. `tradectl accounts status --with-positions --mode live --json > artifacts/emergency_unwind/<ts>/positions_post_close.json`で残存ノーショナルを再計測。
2. `config.emergency.max_residual_notional`を超える場合は、`tradectl emergency hedge --dry-run --profile live-hedge`でヘッジ案を確認。
3. OpsおよびRiskが`--dry-run`結果にサインし、`tradectl emergency hedge --commit --profile live-hedge`を実行。CLI出力を`artifacts/emergency_unwind/<ts>/hedge_commit.json`へ保存。
4. `metrics/emergency_unwind.jsonl`に`hedge_latency_sec`, `hedge_notional`が記録されていることを確認。ヘッジ失敗時は即リトライまたはバックオフィスへエスカレーション。

### 5. 完了確認と証跡整理
1. `tradectl accounts status --with-positions --mode live --json`で`net_exposure<=0.1%·NAV`を満たしたことを確認。達成不能の場合は原因（スリッページ/約定拒否）を記録し、再度手順2〜4を実施するか、Ops Managerがフォールバック方針を記録したうえでリスク委員会へエスカレーション。
2. `tradectl emergency status`で`PB-POS-UNWIND`が`completed`となったことを確認し、`kill_switch_resume_blocked`フラグが`false`であることを`metrics/emergency_unwind.jsonl`から確認する。未完了アクションがある場合は再実行またはIncidentを起票。
3. `tradectl kill-switch review --reason emergency_unwind --strategy all --mode live --recommendation guarded --attachments artifacts/emergency_unwind/<ts>/*.json`を実行し、レビューMarkdownを`reports/audit/kill_switch_review/`へ保存。手動フォールバックを使用した場合は、追加で`reports/audit/manual_unwind_<date>.md`を作成し、ブローカー証跡を添付する。
4. Ops Managerが`reports/validation_log/AC-03_<date>.md`にアンワインド結果とSLA（実測時間、承認者）を追記し、Risk Manager/POがサイン。`ops_worklog.jsonl`へ`task='emergency_unwind'`の所要時間と`mode ∈ {'auto','manual'}`を記録する。

### 6. 再開審査（Kill Switch解除準備）
1. Risk Managerが`tradectl diagnostics risk --from -30d --mode live --export artifacts/emergency_unwind/<ts>/risk_recheck.json`を実施し、R分布・R_effが許容範囲に戻ったか確認。
2. Ops Managerが`tradectl status --kill-switch --board`で`KillSwitchGuard`ロック解除条件（`positions_remaining=0`, `orders_pending=0`）が満たされているかを確認。未満の場合はオーケストレータが`ResumeBlocked`を返すので、その理由をRunbookへ記録。
3. Product Ownerが`tradectl kill-switch review --recommendation resume --attachments ...`を実行し、`tradectl kill-switch set --mode soft_stop(manual_review)`→`tradectl status --ack <id>`で慎重に工程を進める。`KillSwitch: RUNNING`へ戻すのは全サイン済み後のみ。
4. 解除後24時間は`tradectl metrics report --kind emergency_unwind --window 24h`で残存リスクをモニタし、異常時は再度STOPに戻す。

## チェックリスト
- [ ] `KillSwitch: STOP` と `BoardMode: halted` を確認し、ダブルアックを完了した。
- [ ] `tradectl emergency close-all --commit`後に`positions_closed`・`residual_notional`を記録した。
- [ ] `metrics/emergency_unwind.jsonl`で`auto_flatten_duration_sec<=480`または`manual_flatten_duration_sec<=1200`を確認し、Runbookに実測値と判定を記載した。
- [ ] `tradectl emergency cancel-open --commit`で全未約定注文を取消し、失敗があればIncidentを記録した。
- [ ] `net_exposure<=0.1%·NAV`を達成し、必要ヘッジを実行した。
- [ ] `reports/audit/kill_switch_review/<timestamp>.md`に証跡を保存し、Ops/Risk/POがサインした。
- [ ] 手動フォールバック実施時は`reports/audit/manual_unwind_<date>.md`と`evidence/broker/kill_switch/<incident_id>/`を更新した。
- [ ] `reports/validation_log/AC-03_<date>.md`と`ops_worklog.jsonl`を更新した。
- [ ] Kill Switch解除前に`tradectl diagnostics risk`の再検証と`tradectl status --ack`を完了した。

## エスカレーション
- `auto_flatten_duration_sec>480`または自動フローが3分以内に`close_all`/`cancel_open`を完了しない場合は即座に`emergency.auto_commit_enabled=false`へ切替し、Ops/Risk/POへ報告。`RUN-OPS-AGENDA-01`にSLA逸脱を記録し、Quant Leadを呼び出して原因分析を開始する。
- Close-Allが約定拒否/タイムアウトで完了しない場合はブローカーサポートへ即座に連絡し、`tradectl ops incident open --category execution --severity critical`でIncidentを起票。
- 30分以内に`net_exposure`が閾値内へ収束しない場合、リスク委員会（Risk Manager, Ops Manager, Quant Lead, Product Owner, Compliance Advisor）を招集し、追加ヘッジまたはポジション廃棄を決定する。
- ヘッジ口座/API接続が機能しない場合は`RUN-BROKER-API-02`に切り替え、手動でオフセット取引を実施する。
- Kill Switch解除審査でOps/Risk/POのいずれかが承認しない場合はSTOP状態を維持し、解決策が提示されるまでトレード再開を禁止する。

## 履歴・改訂
- v1.0 (2025-03-20): 自動/手動平残SLAと承認マトリクスを追加。`metrics/emergency_unwind.jsonl`の`auto_flatten_duration_sec`/`manual_flatten_duration_sec`取得手順、手動フォールバック証跡（`reports/audit/manual_unwind_<date>.md`）を明記し、エスカレーション基準を更新。
- v0.9 (2025-03-19): 初版ドラフト。Emergency Orchestrator連携とCLIハンドオフを定義。監査ログ/メトリクス運用を記載。
- 改訂時は版数を+0.1し、`reports/governance/runbook_changelog.md`へ記録する。同時に`detailed_design_fx_signal_tool_v1.md §19.3`と突合し、Runbook参照が一致していることを確認する。
