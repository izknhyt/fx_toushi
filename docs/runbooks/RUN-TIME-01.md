# RUN-TIME-01: 時刻同期・タイムゾーン異常対応手順

> **ACカバレッジ**: AC-05, AC-45（時刻整合）
> **Runbook版数**: v0.3
> **最終更新日**: 2025-03-18
> **最終更新者**: Ops Manager (Doc Maintainer)

## 目的
- サーバーおよびオペレータ端末の時刻同期を維持し、ログやレポートのタイムスタンプが整合するようにする。
- `ManualCsvReconciler`や`Board`で検出される`clock_mismatch`アラートへの対応手順を定義する。

## 適用範囲・トリガー
- `metrics/time_sync.jsonl`でドリフトが閾値（±3秒）を超えたとき。
- `ManualCsvError(code='clock_mismatch')`が発生したとき。
- `tradectl preflight --recheck`で時刻同期エラーが出力されたとき。

## 事前準備
- NTPクライアント（例: `sntp`, `chrony`）がインストール済みであること。
- `sudo`権限を持つオペレータが対応可能な状態。
- `reports/validation_log/AC-45_sla_<date>.md`のテンプレートを用意。

## 日次クイックチェック（M1 Core必須）
- 目的: プレフライト警告に頼らず、起動前に人が時計差を把握する。
- 手順:
  1. `systemsetup -getnetworktimeserver`でNTPサーバが設定されていることを確認し、未設定なら`sudo systemsetup -setnetworktimeserver time.apple.com`などで設定する。
  2. `date`コマンドの出力とスマートフォン等の基準時計を比較し、±2秒以内であることを目視確認する。
  3. ±2秒を超える場合は以下の「手順」で再同期を実施し、`tradectl preflight --silent`のWARNログを添付してOps日報に記録する。
> **メモ**: `TimeSyncGuard`自動ガードはM1.1 Hardeningで導入予定のため、M1 Coreではこの手動チェックで十分とする。

## 手順
1. `tradectl preflight --recheck`を実行し、`clock_drift_ms`を確認。
2. サーバーで`sudo sntp -sS time.apple.com`（または`sudo chronyc makestep`）を実行し、NTP同期を強制。
3. 同期後に`timedatectl status`で`System clock synchronized: yes`を確認。
4. `python tools/check_time_drift.py --threshold-ms 2000`で追加チェックを行い、結果を`reports/diagnostics/time_sync/<date>.md`に保存。
5. `tradectl preflight --recheck`を再度実行し、`clock_drift_ms`が閾値内に収まったことを確認。
6. `reports/validation_log/AC-45_sla_<date>.md`へ対応内容とサインを追記し、必要に応じて`tickets/runbooks/RUN-TIME-01/<date>.md`へ詳細を記録。

## Snapshot復旧演習（CHK-0.6.9-6/7）
> 目的: `ModeContext`/`SnapshotManager`の手動検証を定期的に行い、Backtest/Paper/Liveの再起動手順をOps/Quant双方で共有する。

### 実行頻度
- 週次Opsレビュー前（通常は火曜）にBacktest/Paper/Live各1回。
- Acceptable Degradation時は即時再実行し、`docs/development_plan.md#update-log-utc`へタイムスタンプを記録（`docs/archive/risk_review/20250318_prelaunch.md`は参照のみ）。

### 事前準備
- `config/profiles/<mode>.yaml` が最新版であること。
- `snapshots/sessions/<mode>/` に破損ファイルが残っていないことを `git status` または `python tools/verify_parquet.py` で確認。
- `docs/validation/ModeContext_startup.md` の表に次回セッションIDを予約（例: `session-backtest-<date>`）。

### 手順
1. `poetry run python -m tradectl start --profile <mode> --session-id <session>` を実行し、`logs/sessions/<session>.log` に `ctx.mode`, `ctx.profile.name`, `deterministic_seed` が出力されたことを確認。
2. 必要に応じて `--json` を付与し、CLI出力を `reports/validation_log/CHK-0.6.9_mode_context_<date>.md` へ貼り付ける。
3. `poetry run python -m tradectl stop --session-id <session>` を実行し、`snapshots/sessions/<mode>/<session>.json` が生成/更新されたことを確認。
4. `python tools/check_dataset_hash.py --manifest reports/data_manifest.json --strategy m1_baseline_ma_rsi --write reports/risk/20250318_prelaunch/modecontext_snapshot.md --append` を実行し、演習時刻をEvidence化（ハッシュ比較を流用）。
5. `docs/validation/ModeContext_startup.md` の該当行にログ/スナップショットへのリンクを追記し、`[x] Pass` へ更新する。
6. Ops Agenda `docs/runbooks/daily_agenda/<date>.md` → 「ModeContext Startup Walkthrough」欄に本Runbookの参照を貼り付け、Ops ManagerとCodex Liaisonがサインする。

### エラー時の対応
- `snapshots/...json` が破損している場合は直近良品へロールバックし、`git clean` は使用せずリネームで退避。
- `tradectl start` が`config`解決に失敗した場合は`config/profiles/<mode>.yaml`と`ConfigRegistry`差分を確認。再現ログを`logs/ops/modecontext_<date>.log`へ保存し、R-04フォローアップとして`docs/development_plan.md#update-log-utc`に追記（`docs/archive/risk_review/20250318_prelaunch.md`は参照のみ）。

## チェックリスト
- [ ] `tradectl preflight --recheck`前後のログ取得
- [ ] NTP同期コマンド実行結果の記録
- [ ] `timedatectl status`のスクリーンショット/ログ保存
- [ ] `reports/diagnostics/time_sync/<date>.md`の更新
- [ ] `reports/validation_log/AC-45_sla_<date>.md`へのサイン

## エスカレーション
- NTP同期が繰り返し失敗する場合は`docs/runbooks/OPS-READINESS-01.md`の緊急対応を起動し、代替サーバーへの切替を検討。
- 手動CSVで時刻不整合が続く場合はデータ提供者へ連絡し、`docs/runbooks/RUN-DATA-05.md`に従って補正データを取得。

## 履歴更新手順
- Runbookを改訂した際は版数・最終更新日・更新者を更新し、`reports/governance/runbook_changelog.md`へ記録。
- Validation Data Playbook（要件定義§8.2, AC-45行）へRunbook版数を反映する。
