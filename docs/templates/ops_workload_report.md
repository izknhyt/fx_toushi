<!-- Ops Workload monthly report template. See 詳細設計 §18.3 Opsワークロードレポートテンプレ for structure. -->
# Ops Workload Report ({{report.period}})

- **Generated Via**: `tradectl ops workload report --period {{report.period}} --from-json metrics/ops_workload.json`
- **Total Minutes**: {{report.totals.minutes}}
- **Automation Gain (Minutes)**: {{report.totals.automation_gain_min}}
- **Reference**: [詳細設計 §18.3 Opsワークロードレポートテンプレ](../../detailed_design_fx_signal_tool_v1.md#183-opsワークロードレポートテンプレ-toolsops_workload_reportpy)
- **Supporting Metrics**: `metrics/ops_workload.json`
- **Validation Evidence**: `reports/validation_log/AC-51_ops_{{report.period}}.md`

## Summary
| Item | Detail |
| --- | --- |
| Peak Load Drivers | {{summary.peak_load_drivers}} |
| Automation Highlights | {{summary.automation_highlights}} |
| Capacity Alerts | {{summary.capacity_alerts}} |
| Pending Follow-ups | {{summary.follow_ups}} |
| Notes | {{summary.notes}} |

## Breakdown by Task
| Task | Samples | Total Minutes | Median (min) | P90 (min) | Automation Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
{{#breakdown.tasks}}
| {{task}} | {{samples}} | {{total_min}} | {{median_min}} | {{p90_min}} | {{automation_status}} | {{notes}} |
{{/breakdown.tasks}}

## Automation Candidates
> List tasks where `automation_effect` has not yet met the threshold or requires additional validation.

| Task | Current Gain (min) | Threshold (min) | Next Action | Owner | Target Date |
| --- | --- | --- | --- | --- | --- |
{{#automation_candidates}}
| {{task}} | {{current_gain_min}} | {{threshold_min}} | {{next_action}} | {{owner}} | {{target_date}} |
{{/automation_candidates}}

## Runbook Notes
> Capture Runbook updates, overdue reviews, and required DocOps follow-ups (詳細設計 §52.3/§52.5).

- {{runbook_notes.item_1}}
- {{runbook_notes.item_2}}
- {{runbook_notes.item_3}}

## Evidence & Distribution
- 保存先: `reports/ops/workload/{{report.period}}.md`
- JSONソース: `metrics/ops_workload.json`
- Runbook: [RUN-OPS-LOG-01](../runbooks/RUN-OPS-LOG-01.md)
- Related Agenda: `reports/ops/daily_agenda/{{report.latest_agenda_date}}.md`

> Codexはレポート生成後に`ops_worklog`エントリを`task='workload_report'`として追記し、Opsレビュー会議で共有すること。
