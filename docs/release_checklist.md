# Release Checklist (Template)

リリース前に必ず以下を確認し、署名を残す。Runbookと証跡パスは詳細設計 §8.8 / §13 / §31 と整合させる。
このチェックリストは`tradectl release prepare --version <tag>`で読み込まれるため、更新後はCLIの出力に反映される。進捗は`tradectl release record`で記録する。

## 1. リスク・コンプライアンス
- [ ] `risk_state.json` が `status: accepted` で `consent_reference_id` / `accepted_at` がセットされている（consent_reference_id=`<id>`）
- [ ] `docs/change_requests/` の未クローズ項目なし（CR-<id>）
- [ ] Kill Switch/Spread/Reduce-Only 状態が `tradectl status --json` で正常（Exit Code 0 または 21）である証跡: `reports/validation_log/release_status_<date>.json`

## 2. テスト・品質
- [ ] `pytest -k smoke` 実行結果を添付（ログまたはサマリ）: `reports/implementation/<date>_smoke.log`
- [ ] Packet対応テストが緑（config_schema_smoke / strategy_determinism / strategy_manifest / ticket_builder / json_schema_validation）
- [ ] Lint/format: `ruff <version>` と `black --check <version>` の結果を記録

## 3. データ・設定
- [ ] `config/` の変更は `schema-validate` 済み（証跡: `reports/validation_log/config_schema_<date>.json`）
- [ ] スナップショット/バックアップ最新: `snapshots/latest/gate_state.json`（更新時刻を記載）
- [ ] `metrics/guardrails.jsonl` 最新行に `exit_code` / `spread_status` / `reduce_only` が記録されている

## 4. 運用・Runbook
- [ ] `tradectl status --json` 出力をRunbookに添付（`RUN-DATA-05`/`RUN-RISK-02`）: `reports/validation_log/release_status_<date>.json`
- [ ] `tradectl resync --failover-report` の最新証跡: `reports/ops/resync/<date>.md`
- [ ] 日次/週次アジェンダ連携: `docs/runbooks/daily_agenda/*.md` にオープン項目なし
- [ ] メトリクス清掃cron登録（毎日03:00）と手動初回実行: `logs/cleanup/metrics_<date>.log`

## 5. Lint/Format
- [ ] `ruff <version>` 実行（既存違反数と差分扱いを記録）
- [ ] `black --check <version>` 実行（要整形ファイル数を記録）

## 6. 承認
- [ ] Product Owner: ____________________ Date: __________
- [ ] Ops Manager: ____________________ Date: __________
- [ ] Risk Officer (必要に応じて): ____________________ Date: __________

## 備考
- Hands-off/auto_execute はデフォルト無効。`check-profit-readiness-hands-off-all`が緑かつOps判断でのみ有効化する。
- 動的補正は`src/execution/alpha_overlay.apply_hands_off_sizing`を経由し、CIゲートは`check-profit-readiness-hands-off-all`で担保する。

## 付録
- 参考コマンド: `poetry run pytest -k smoke`, `poetry run schema-validate config/*.yaml --schema docs/schemas/*.json`, `python -m tradectl status --json`, `python -m tradectl resync --failover-report --json`
