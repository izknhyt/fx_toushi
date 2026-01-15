# RUN-LIQ-01: 流動性乖離アラート対応

> **ACカバレッジ**: AC-22, AC-49（流動性・スプレッド関連）
> **Runbook版数**: v0.1
> **最終更新日**: 2026-01-12
> **最終更新者**: Risk Manager (Doc Maintainer)

## 目的
- `LiquidityMonitorService`が乖離・更新遅延・スプレッド異常を検知した際に、Reduce-Only/BoardMode判断と証跡作成を行う。
- `reports/validation_log/liquidity_alert_<date>.md`と`ops_worklog.jsonl`を確実に残し、後続レビューに接続する。

## 適用範囲・トリガー
- `liquidity.alert`が発火したとき。
- `tradectl liquidity status`で`state=guarded/halted`を確認したとき。

## 事前準備
- `docs/runbooks/RUN-SPREAD-03.md`と`docs/runbooks/RUN-DATA-05.md`を参照可能にしておく。
- `snapshots/latest/liquidity_state.json`と`snapshots/latest/gate_state.json`の最新を確認。

## 手順
1. `tradectl liquidity status --json`で最新スナップショットを取得し、`state`/`recommendation`を確認。
2. `reports/validation_log/liquidity_alert_<YYYYMMDD>.md`にアラート内容（alert_id/metrics/対応方針）を追記。
3. `board_mode=guarded`が必要な場合は`tradectl board --guarded --liquidity-status guarded`を実行し、Boardバナーの表示を確認。
4. 乖離が解消したら`tradectl liquidity status`で`state=normal`を確認し、解除時刻を記録。
5. `ops_worklog.jsonl`に対応時間と結論を記録する（自動記録があれば追記のみ）。

## チェックリスト
- [ ] `tradectl liquidity status`で状態確認
- [ ] `liquidity_alert_<date>.md`の更新
- [ ] Boardバナー確認（guarded時）
- [ ] 解除後の状態確認と記録

## エスカレーション
- `halted`が30分以上続く場合はRisk Managerへエスカレート。
- データソース障害が疑われる場合は`RUN-DATA-05`のManual CSV手順へ移行。

## 履歴更新手順
- Runbook改訂時は版数・最終更新日・更新者を更新し、`reports/governance/runbook_changelog.md`へ履歴を追記。
