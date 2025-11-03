# AC-45 Weekly Validation Evidence Template

## メタデータ
- Week: <YYYY-WW>
- Generated at: <YYYY-MM-DD HH:MM JST>
- Prepared by: <name>
- Reviewed by: <name>

## 0. CLI & Snapshot Commands
- `tradectl report weekly --dry-run --week <YYYY-WW> --save-snapshot reports/weekly/evidence/<YYYY-WW>/report.json`
- `tradectl board --view strategy --strategy-id <strategy_id> --save-snapshot reports/weekly/evidence/<YYYY-WW>/board_snapshot.json`
- `tools/metrics_extract.py --source metrics/strategy_execution.jsonl --window 7d --out reports/weekly/evidence/<YYYY-WW>/strategy_execution.md`
- `tradectl performance live-guard --strategy <strategy_id> --window 4w --mode <mode> --output json --strict --save reports/weekly/evidence/<YYYY-WW>/live_guard.json`
- `make check-ops-readiness` → ログ: reports/validation_log/ops_readiness_<YYYY-WW>.md
- `poetry run schema-validate config --schema docs/schemas/config_bundle.schema.json`
- `pytest -k "weekly_report or config_schema_smoke"`

## 1. Signal Cycle Evidence
- signal_cycle_snapshot: reports/weekly/evidence/<YYYY-WW>/board_snapshot.json
- strategy_execution_extract: reports/weekly/evidence/<YYYY-WW>/strategy_execution.md
- live_guard_snapshot: reports/weekly/evidence/<YYYY-WW>/live_guard.json
- ops_readiness_validation: reports/validation_log/ops_readiness_<YYYY-WW>.md
- log_samples:
  - logs/signals/raw/<YYYYMMDD>.jsonl#line
  - metrics/performance_live_guard.jsonl#line
  - logs/health/events.jsonl#line

## 2. Metrics Summary
| Metric | Value | Threshold | State | Notes |
| --- | --- | --- | --- | --- |
| Sharpe trailing | <value> | <threshold> | <state> | <note> |
| PF trailing | <value> | <threshold> | <state> | <note> |
| Latency p75 | <value> | <threshold> | <state> | <note> |
| Ops readiness score | <value> | <min_score>/<warn_score> | <state> | <note> |
| data_ingestion_sla | <value> | <threshold> | <state> | <note> |

## 3. Runbook & Escalation Links
- RUN-PERF-01 checklist: <path>
- RUN-RISK-01 checklist: <path>
- RUN-RISK-07 live guard actions: <path>
- RUN-EXEC-02 calibration log: <path>
- OPS-READINESS-01 evidence: <path>
- CONFIG-SCAFF-01 diff (必要に応じて): <path>

## 4. Reviewer Comments
- Risk Manager:
- Ops Manager:
- Trader Lead:
- Product Owner:

## 5. Follow-up Items
- [ ] Item
- [ ] Item
- [ ] Live Guard mitigation ticket: tickets/live_guard_followup/<date>.md

## 6. 更新履歴
- 2025-03-23: Runbooks/CLI/Evidence項目を追加し、Live GuardおよびOps Readiness整合を反映。
- 2025-03-12: Template created via SEレビュー（§0.6.11, §7.6）
