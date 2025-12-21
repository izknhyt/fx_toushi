# Release Checklist (M1)

リリース前に必ず以下を確認し、署名を残す。Runbookと証跡パスは詳細設計 §8.8 / §13 / §31 と整合させる。

## 1. リスク・コンプライアンス
- [x] `risk_state.json` が `status: accepted` で `consent_reference_id` / `accepted_at` がセットされている（consent_reference_id=`consent-ops-20251216`）
- [x] `docs/change_requests/` の未クローズ項目なし（CR-20251122-hands-off-auto-execute.md は完了）
- [x] Kill Switch/Spread/Reduce-Only 状態が `tradectl status --json` で正常（Exit Code 0 または 21）である証跡: `reports/validation_log/release_status_20251216.json`

## 2. テスト・品質
- [x] `pytest -k smoke` 実行結果を添付（ログまたはサマリ）: `reports/implementation/20251216_smoke.log`
- [x] Packet対応テストが緑（config_schema_smoke / strategy_determinism / strategy_manifest / ticket_builder / json_schema_validation）
- [ ] Lint/format: `ruff 0.14.2` 実行→既存違反 ~1100件で失敗（未修正、出力はCLI参照）。`black --check 23.12.1` 実行→129ファイル要整形＋1ファイル構文エラー（未修正）。

## 3. データ・設定
- [x] `config/` の変更は `schema-validate` 済み（証跡: `reports/validation_log/config_schema_20251216.json`）
- [x] スナップショット/バックアップ最新: `snapshots/latest/gate_state.json` (Dec 07 11:46:27 2025)
- [x] `metrics/guardrails.jsonl` 最新行に `exit_code` / `spread_status` / `reduce_only` が記録されている

## 4. 運用・Runbook
- [x] `tradectl status --json` 出力をRunbookに添付（`RUN-DATA-05`/`RUN-RISK-02`）: `reports/validation_log/release_status_20251216.json`
- [x] `tradectl resync --failover-report` の最新証跡: `reports/ops/resync/20251216.md`
- [x] 日次/週次アジェンダ連携: `docs/runbooks/daily_agenda/*.md` にオープン項目なし
- [x] メトリクス清掃cron登録（毎日03:00）と手動初回実行: `logs/cleanup/metrics_20251216.log`

## 6. Lint/Format
- [ ] `ruff 0.14.2` 実行（既存違反多数で失敗、未修正）
- [ ] `black --check 23.12.1` 実行（129ファイル要整形＋1ファイル構文エラー、未修正）

## 備考
- Hands-off/auto_execute はデフォルト無効。`check-profit-readiness-hands-off-all`が緑かつOps判断でのみ有効化する（CR-20251122完了）。
- 動的補正は`src/execution/alpha_overlay.apply_hands_off_sizing`を経由し、CIゲートは`check-profit-readiness-hands-off-all`で担保する。

## 5. 承認
- [x] Product Owner: izumimotohayato Date: 2025-12-16
- [x] Ops Manager: izumimotohayato Date: 2025-12-16
- [ ] Risk Officer (必要に応じて): ____________________ Date: __________

## 付録
- 参考コマンド: `poetry run pytest -k smoke`, `poetry run schema-validate config/*.yaml --schema docs/schemas/*.json`, `python -m tradectl status --json`, `python -m tradectl resync --failover-report --json`

## 未完・注記
- Lint/Format（ruff/black）は実行したが既存違反多数のため未修正。承認時に差分扱い（今後のフォローアップ）を確認すること。
- Hands-off用CIゲート `make check-profit-readiness-hands-off-all` は昇格させる場合に必須。
