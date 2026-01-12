<!-- このテンプレートはReporterがM1 Core週次レポートを生成する際の基準です。 -->
# Weekly Performance Report (M1 Core)

> 実体ファイル: `reports/weekly/templates/m1_core.md`。更新時は両者を同期させること。

- **Week**: {{report_week}} (`YYYY-WW`)
- **Generated at**: {{generated_at_jst}} (JST)
- **Profile / Mode**: {{profile}} / {{mode}}
- **KPI Snapshot Version**: {{kpi_snapshot_version}}
- **Metric Window**: 90営業日ローリング（M1 Core）

## KPI Summary
| Metric | Value | Metric State | Notes |
| --- | --- | --- | --- |
| Sharpe Ratio | {{metrics.sharpe.value}} | {{metrics.sharpe.state}} | {{metrics.sharpe.note}} |
| Max Drawdown | {{metrics.max_drawdown.value}} | {{metrics.max_drawdown.state}} | {{metrics.max_drawdown.note}} |
| Win Rate | {{metrics.win_rate.value}} | {{metrics.win_rate.state}} | {{metrics.win_rate.note}} |
| Cumulative R | {{metrics.cumulative_r.value}} | {{metrics.cumulative_r.state}} | {{metrics.cumulative_r.note}} |

> **データ出典**: `reports/performance/{{mode}}/{{report_week}}/*.parquet`, `reports/kpi_snapshots/{{report_week}}.json`

## Ops Evidence Checklist
- `tradectl report weekly --dry-run --week {{report_week}} --save-snapshot reports/weekly/evidence/{{report_week}}/report.json`
- `tradectl board --view strategy --strategy-id {{strategy_id}} --save-snapshot reports/weekly/evidence/{{report_week}}/board_snapshot.json`
- `tools/metrics_extract.py --source metrics/strategy_execution.jsonl --window 7d --out reports/weekly/evidence/{{report_week}}/strategy_execution.md`
- `tradectl performance live-guard --strategy {{strategy_id}} --window 4w --mode {{mode}} --output json --strict --save reports/weekly/evidence/{{report_week}}/live_guard.json`
- `make check-ops-readiness` → ログ: `reports/validation_log/ops_readiness_{{report_week}}.md`

## Signal Cycle Evidence
| Evidence | Path | Owner | Notes |
| --- | --- | --- | --- |
| Signal Board snapshot | `reports/weekly/evidence/{{report_week}}/board_snapshot.json` | Ops | `tradectl board --view strategy --strategy-id {{strategy_id}}` |
| Strategy execution extract | `reports/weekly/evidence/{{report_week}}/strategy_execution.md` | Quant | `tools/metrics_extract.py` |
| Live Guard result | `reports/weekly/evidence/{{report_week}}/live_guard.json` | Risk | `tradectl performance live-guard --strategy {{strategy_id}} --strict` |
| Ops readiness validation | `reports/validation_log/ops_readiness_{{report_week}}.md` | Ops | `make check-ops-readiness` |

## Live Guard Watch
| Metric | Value | Threshold | State | Notes |
| --- | --- | --- | --- | --- |
| PF trailing | {{live_guard.pf_trailing.value}} | {{live_guard.pf_trailing.threshold}} | {{live_guard.pf_trailing.state}} | {{live_guard.pf_trailing.note}} |
| Sharpe trailing | {{live_guard.sharpe_trailing.value}} | {{live_guard.sharpe_trailing.threshold}} | {{live_guard.sharpe_trailing.state}} | {{live_guard.sharpe_trailing.note}} |
| Latency p75 | {{live_guard.latency_p75.value}} | {{live_guard.latency_p75.threshold}} | {{live_guard.latency_p75.state}} | {{live_guard.latency_p75.note}} |
| Alerts | {{live_guard.alerts}} | - | {{live_guard.status}} | {{live_guard.recommended_action}} |

## Risk Disclosure
| Item | Status | Expires At | Last Accepted By | Consent Ref |
| --- | --- | --- | --- | --- |
| Model Risk Statement | {{risk_disclosure.status}} | {{risk_disclosure.expires_at}} | {{risk_disclosure.last_accepted_by}} | {{risk_disclosure.consent_reference_id}} |

## Incident & Alerts Summary
- Acceptable Degradation: {{degradation.summary}}
- Kill Switch Reviews: `reports/audit/kill_switch_review/`
- Outstanding Tickets: {{open_tickets}}

## Kill Switch & Spread
- Kill Switch history: {{kill_switch.history}}
- Spread cooldown summary: {{spread.cooldown_summary}}

## Manual CSV & Data Quality
- Manual CSV summary: {{manual_csv.summary}}
- Data quality summary: {{data_quality.summary}}
- Resync summary: {{resync.summary}}
<!-- deferred: M1.1 -->

## Ops Worklog Excerpt
{{ops_worklog_excerpt}}

## Manual Commentary

### A/Bテスト結果（担当: Quant Lead / 締切: 日曜 18:00 JST）
- レビュー記録: `docs/development_plan.md#update-log-utc` の `AB-{{report_week}}`
- Runbook参照: `docs/runbooks/STRAT-M1-VALIDATION.md`
- サマリ:
  - 実施テスト: 
  - 勝者/判断理由: 
  - 次アクション: 

### 次週ToDo（担当: Ops Manager / 締切: 月曜 08:30 JST）
- レビュー記録: `docs/development_plan.md#update-log-utc` の `OPS-{{report_week}}`
- Runbook参照: `docs/runbooks/RUN-PERF-01.md`, `docs/runbooks/RUN-RISK-01.md`, `docs/runbooks/RUN-RISK-07.md`, `docs/runbooks/OPS-READINESS-01.md`
- サマリ:
  - 優先タスク: 
  - 所要Runbook/チケット: 
  - Opsアジェンダ連携: `tradectl ops agenda --date <YYYY-MM-DD>` で生成

## Attachments & Links
- Validation Logs: `reports/validation_log/AC-45_sla_*.md`
- Live Guard Actions: `reports/validation_log/live_guard_*.md`
- Ops Readiness: `reports/validation_log/ops_readiness_{{report_week}}.md`
- Ops Worklog Snapshot: `metrics/ops_workload.json`
- Feature Flags: `config/profile_{{profile}}.yaml`

## Sign-off
- Prepared by:
- Reviewed by:
- Approved by:

> コメント欄は締切後の修正を禁止し、差分は`docs/development_plan.md#update-log-utc`に追記すること。
