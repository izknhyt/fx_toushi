# Weekly Performance Report (M1+)

- **Week**: {{report_week}} (`YYYY-WW`)
- **Generated at**: {{generated_at_jst}} (JST)
- **Profile / Mode**: {{profile}} / {{mode}}

## Coaching Summary
- Approval latency (sec): {{coaching.avg_approval_latency_sec}}
- Checklist completion rate: {{coaching.checklist_completion_rate}}
- Guarded time ratio: {{coaching.guarded_time_ratio}}
- Mistake rate: {{coaching.mistake_rate}}
- Over-threshold insights: {{coaching.over_threshold_count}}

## Degradation Summary
- Acceptable Degradation: {degradation_summary}

## Ops Evidence
- `reports/ops/coaching/<YYYYWW>_summary.md`
- `reports/ops/coaching/<YYYYWW>_insights.md`
- `metrics/trader_workflow.jsonl`
- `metrics/coaching_insights.jsonl`
