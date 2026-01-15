# RUN-FUND-02: Fundingデグレ対応

> **最終更新日**: 2026-01-12
> **最終更新者**: Codex (Doc Maintainer)

## 目的
`FundingDegraded`イベント発生時にPaper損益の誤差を最小化し、復旧証跡を完全に残す。

## トリガー
- `health.raise('degraded','funding_data_gap')`イベント
- `tradectl funding status`で`shadow_reconciliation = FAIL`
- `funding_state.json.last_synced_at`が48時間超過

## 手順
1. `tradectl funding status --json > evidence/funding_status_<timestamp>.json`を実行し、現状を保存する。
2. `reports/validation_log/AC-09_funding_<date>.md`の「Incident Log」に発生日、検知者、影響推定（想定PnL差）を記入する。
3. Ops/Riskが`config/swap_rates.csv`と`reports/funding/swap_rates_shadow.csv`を更新し、Runbook `RUN-FUND-01`のStep 1-3を再実施する。
4. CLI `tradectl funding sync --shadow reports/funding/swap_rates_shadow.csv`を再実行し、イニシャルとハッシュ値を記録する。同期が成功したら、CLI出力と`funding_state.json`を`reports/validation_log/`と`reports/funding/`に保存し、`reports/funding/daily_hash_log.md`へ復旧日のハッシュ値とリンクを追記する。進捗は`docs/development_plan.md#update-log-utc`に記録する。
5. POが`reports/validation_log/AC-09_funding_<date>.md`の「Recovery Sign-off」にイニシャルを記入し、`tradectl health ack --reason funding_data_gap`を実行する。
6. `reports/ops/degradation_log/<YYYYMMDD>.md`へ影響ペア、対応時間、再発防止策を追記し、週次Ops会議でレビューする。

## チェックポイント
- `shadow_reconciliation`が`PASS`へ戻ったか。
- `funding_state.json`の`csv_sha256`/`shadow_sha256`が一致し、更新時刻が復旧時刻を指しているか。
- Runbook `RUN-FUND-01`のチェックリストが再実施済みか。

## 付録
- 関連Runbook: `RUN-FUND-01`
- 参照セクション: §3.12.1, §5.15.1
