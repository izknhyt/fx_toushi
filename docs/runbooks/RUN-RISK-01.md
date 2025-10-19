# RUN-RISK-01: Kill Switch・リスク監視運用手順

> **ACカバレッジ**: AC-03, AC-09  
> **Runbook版数**: v1.1
> **最終更新日**: 2025-03-09
> **最終更新者**: Risk Manager (Doc Maintainer)

## 目的
- 日次-2.5% / 週次-5%のドローダウン閾値到達時にKill Switchを確実に発火させ、再開には所定の承認手続きを強制する。
- R分布・同時保有数・R_eff制約を定期的に検証し、受け入れ基準AC-03およびAC-09のコンプライアンスを維持する。
- Validation Data Playbook（AC-09）に沿って`data/correlation/`配下の相関データセットを週次で更新し、Signal BoardとRisk Managerの指標整合を保つ。
- リスク関連インシデントのログと是正措置を`reports/audit/`配下に残し、監査対応時のトレーサビリティを確保する。

## 適用範囲・トリガー
- 日次モーニングチェック（Ops Managerが実施）。
- `HealthMonitor`が`soft_stop`/`kill_switch`ステータスへ遷移したとき。
- `tradectl diagnostics risk`が閾値逸脱を検出したとき、またはAC-03/AC-09の受け入れテストを実行するとき。

## 事前準備
- `risk_policy.yaml`と`ops_schedule.yaml`が最新コミットと一致していること。
- `reports/audit/drawdown_guard/`と`reports/performance/paper/latency_stats.json`への書き込み権限を確認する。
- Kill Switch解除権限を持つプロダクトオーナーがSlack/電話で即応できる体制。

## 手順

### 1. 日次リスクサマリ確認（平常時）
1. `tradectl status --history kill-switch --limit 7` を実行し、直近7日間のKill Switchイベントを確認。`state=armed`のままになっていないかチェックする。
2. `tradectl diagnostics risk --from -7d --mode paper` を実行し、`per_trade_R_stdev`が`0.70〜0.80`に収まっているか、`max_concurrent`違反が0件かを確認する。
3. `tradectl metrics latency --mode paper --from -1d`で承認→OCOレイテンシの中央値/p90を確認し、AC-09の閾値内であることを記録する。
4. 結果を`reports/validation_log/AC-09_<date>.md`へ追記し、担当者サインを残す。

### 2. ドローダウン閾値到達時の対応（AC-03）
1. `HealthMonitor`またはアラートで`drawdown_daily>=2.5%`または`drawdown_weekly>=5%`が通知されたら、即座に`tradectl risk limits show --mode paper`で現在値を確認する。
2. `tradectl kill-switch engage --mode paper --reason drawdown` を実行し、状態が`soft_stop`/`hard_stop`に遷移したことを`tradectl status`で確認する。自動発火済みの場合は二重実行しない。
3. `reports/audit/drawdown_guard/<YYYYMMDD>.md`を作成し、
   - 発生日/時刻
   - シンボル別損失内訳
   - 閾値判定ログ（`logs/events/risk.kill_switch_*.jsonl`）
   - Kill Switch操作の実行者・理由
   を記録する。
4. Risk Managerが原因分析（戦略別寄与、想定外スリッページ有無）を行い、緩和アクション（Reduce-Only、サイズ縮小等）を提示する。
5. プロダクトオーナーおよびOps Managerが復帰判断会議を開催し、議事録を上記Markdownへ追記する。再開までに以下を満たすこと:
   - `tradectl diagnostics risk --from -30d`でR分布/同時保有数が基準内
   - `reports/performance/paper/latency_stats.json`で遅延閾値内
   - 是正タスクが`tickets/model_revalidate/`等で起票済み
6. 条件が満たされたら`tradectl kill-switch release --mode paper --ticket <issue_id>`を実行し、解除ログを記録する。解除後24時間は`tradectl diagnostics risk --from -1d --interval 1h`で監視を継続する。

### 3. R_eff監視とアラート処理（AC-09）
1. `tradectl diagnostics risk --from -1d --mode paper --detail`で`R_eff`のピーク値を確認し、`max_r_eff`が`≤2.5`であることを確認する。Signal Boardヘッダの`R_eff`バナー（Risk Metrics Snapshot）が同値であるか突合する。
2. `R_eff`が閾値を超過した場合は`tradectl risk override --block --reason r_eff_breach --duration 60m`で新規シグナル投入を停止し、Ticket Builderへ通知する。Signal Boardの赤バナーが消えるまで（連続2バー≒10分）Kill Switchを維持し、解除時は`reason=r_eff_guard`で記録する。
3. `reports/diagnostics/risk/<YYYYMMDD>.json`を更新し、閾値逸脱のグラフ/統計と`RiskMetricsSnapshot`のハッシュを添付する。`reports/validation_log/AC-09_<date>.md`にエビデンスを追記。
4. 逸脱原因を調査し、ポジションサイズの異常・設定不整合があれば`risk_policy.yaml`修正を提案。対応完了までKill Switchを保持する。

### 4. 週次レビュー
1. `tradectl risk summary --week`を実行し、週次ドローダウン・R_eff・同時保有率をレポートにまとめる。
2. 週次Ops会議でRunbook手順の完了チェックリストを確認し、未完了項目があれば`reports/governance/ops_readiness_<YYYYWW>.md`に記載する。
3. `reports/validation_log/AC-03_<date>.md`に週次レビュー結果と参加者サインを残す。

### 5. 通貨バケット・相関データセット更新（週次 / Paper運用期間）
1. 日曜JST 22:00（マーケットクローズ後）に`tradectl correlation snapshot --window 30d --out data/correlation/$(date +%G%V)_correlation.parquet --heatmap data/correlation/$(date +%G%V)_heatmap.png`を実行する。成功終了コードを確認し、生成ファイルのSHA256を`reports/validation_log/AC-09_<date>.md`に追記する。
2. `tradectl board --view risk`でSignal Boardの`R_eff`バナー時刻が最新スナップショットと一致しているかを確認する。バナーが更新されない場合は`tradectl events tail --type risk_metrics_snapshot --since -15m`でイベント遅延を確認し、必要に応じて`tradectl board`を再起動して反映させる。
3. `tradectl diagnostics risk --from -30d --mode paper --export reports/diagnostics/risk/<YYYYWW>.json`を実行し、`r_eff_time_series`と`bucket_exposures`が新しいParquetと一致していることを確認する。
4. Validation Data Playbook（要件定義§8.2, AC-09行）に従い、Risk ManagerとOps Managerが`reports/validation_log/AC-09_<date>.md`へ更新者・実行コマンド・ファイルハッシュ・差分要約を記録する。必要に応じて`tradectl correlation diff --base data/correlation/initial/bootstrap.parquet --target data/correlation/$(date +%G%V)_correlation.parquet`で基準データとの差分を確認し、バケット閾値の逸脱があれば是正タスクを起票する。

## チェックリスト
- [ ] 日次`tradectl diagnostics risk`でR分布/同時保有数の基準確認（Signal Boardバナーと突合）
- [ ] Kill Switch発火時に`reports/audit/drawdown_guard/<date>.md`を作成
- [ ] 解除前に是正タスクと`tradectl diagnostics risk --from -30d`の結果を確認
- [ ] `R_eff`逸脱時のブロック操作と原因分析ログを保存（`RiskMetricsSnapshot`ハッシュ添付）
- [ ] 週次`tradectl correlation snapshot`実行とValidation Data Playbookへの更新記録
- [ ] 週次レビューでRunbook完了をサインオフ

## エスカレーション
- Kill Switch解除条件が満たせない場合はプロダクトオーナーの承認が得られるまで停止状態を維持し、必要に応じて`Emergency Orchestrator`（Runbook `docs/runbooks/OPS-READINESS-01.md`）を起動する。
- R_eff逸脱が24時間以内に解消しない場合、リスク委員会（Risk Manager, Ops Manager, Quant Lead, Compliance Advisor）を招集し、戦略停止またはパラメータ修正を決定する。

## 履歴更新手順
- Runbook改訂時は版数を+0.1し、最終更新者・日付を反映する。
- 変更履歴を`reports/governance/runbook_changelog.md`に追記し、Validation Data Playbook表（要件定義§8.2）内のRunbook欄を更新する。
