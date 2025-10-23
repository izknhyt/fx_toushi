# Weekly Performance Report (M1 Core)

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

## Manual Commentary

### A/Bテスト結果（担当: Quant Lead / 締切: 日曜 18:00 JST）
- レビュー記録: `docs/review_log.md` の `AB-{{report_week}}`
- Runbook参照: `docs/runbooks/STRAT-M1-VALIDATION.md`
- サマリ:
  - 実施テスト: 
  - 勝者/判断理由: 
  - 次アクション: 

### 次週ToDo（担当: Ops Manager / 締切: 月曜 08:30 JST）
- レビュー記録: `docs/review_log.md` の `OPS-{{report_week}}`
- Runbook参照: `docs/runbooks/RUN-PERF-01.md`, `docs/runbooks/RUN-RISK-01.md`
- サマリ:
  - 優先タスク: 
  - 所要Runbook/チケット: 
  - Opsアジェンダ連携: `tradectl ops agenda --date <YYYY-MM-DD>` で生成

## Attachments & Links
- Validation Logs: `reports/validation_log/AC-45_sla_*.md`
- Ops Worklog Snapshot: `metrics/ops_workload.json`
- Feature Flags: `config/profile_{{profile}}.yaml`

> コメント欄は締切後の修正を禁止し、差分は`docs/review_log.md`に追記すること。
