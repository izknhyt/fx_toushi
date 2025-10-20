# RUN-TIME-01: 時刻同期・タイムゾーン異常対応手順

> **ACカバレッジ**: AC-05, AC-45（時刻整合）
> **Runbook版数**: v0.1
> **最終更新日**: 2025-03-10
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

## 手順
1. `tradectl preflight --recheck`を実行し、`clock_drift_ms`を確認。
2. サーバーで`sudo sntp -sS time.apple.com`（または`sudo chronyc makestep`）を実行し、NTP同期を強制。
3. 同期後に`timedatectl status`で`System clock synchronized: yes`を確認。
4. `python tools/check_time_drift.py --threshold-ms 2000`で追加チェックを行い、結果を`reports/diagnostics/time_sync/<date>.md`に保存。
5. `tradectl preflight --recheck`を再度実行し、`clock_drift_ms`が閾値内に収まったことを確認。
6. `reports/validation_log/AC-45_sla_<date>.md`へ対応内容とサインを追記し、必要に応じて`tickets/runbooks/RUN-TIME-01/<date>.md`へ詳細を記録。

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
