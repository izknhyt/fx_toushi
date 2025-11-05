# Change Requests

運用レビューやKPIレビューで発生したフォローアップタスクを記録するディレクトリ。`CR-<YYYYMMDD>-<slug>.md`形式で起票し、背景・対応者・期日・関連Runbook/レポートを明記する。`detailed_design_fx_signal_tool_v1.md` §13.5 の手順に従い、月次レビューで必要タスクをここへ登録する。

## Performance Snapshot Schema Breaking Change フロー

1. `docs/schemas/performance_snapshot.schema.json` に後方互換性の無い変更を加える場合、事前に `docs/change_requests/` へ `CR-<date>-perf-snapshot.md` を起票し、影響モード（backtest/paper/live）と KPI ゲートの逸脱影響を整理する。
2. `docs/schemas/examples/performance_snapshot.sample.json` を同時に更新し、`tests/contracts/test_performance_snapshot_schema.py` の肯定/否定シナリオを拡張する。PR では `pytest -k contracts` のログと `make contract-performance-snapshot` の結果を CR へ添付する。
3. tradectl/Reporter フローへ影響する場合は `tradectl kpi snapshot` / `tradectl report weekly` のサンプル出力を差し替え、Runbook `RUN-PERF-01` と詳細設計 §7.6 の参照先を CR で確認する。
4. Ops Manager と Risk Lead のダブルサイン後に master へマージし、CR を `status=closed` へ更新する。Breaking Change は週次レビュー（Ops Agenda）で報告し、期間中の reviewer を CR 記録へ明示する。
