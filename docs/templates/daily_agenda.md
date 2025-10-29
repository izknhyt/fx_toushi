<!-- Ops Agenda generation template. See 詳細設計 §52.3 OpsAgendaService for required sections. -->
# Daily Ops Agenda

- **Date (JST)**: {{agenda.date}}
- **Generated Via**: `tradectl ops agenda --date {{agenda.date_cli}}`
- **Health Status**: {{agenda.health_state}}
- **Board Mode**: {{agenda.board_mode}}
- **Kill Switch**: {{agenda.kill_switch_state}}
- **Ops Workload (Prev. Day, min)**: {{agenda.workload_total_min}}
- **Automation Gain (Prev. Day, min)**: {{agenda.automation_gain_min}}
- **Source Files**: `ops_worklog.jsonl`, `automation_effect.jsonl`, `reports/governance/runbook_inventory_status.json`
- **Reference**: [詳細設計 §52.3 OpsAgendaService](../../detailed_design_fx_signal_tool_v1.md#523-opsagendaservice-srcopsagendapy)

## Summary
| Item | Detail |
| --- | --- |
| Ops Worklog Snapshot | {{summary.worklog_snapshot}} |
| Key Alerts / Health Reasons | {{summary.health_reasons}} |
| Pending Validation Items | {{summary.validation_pending}} |
| Upcoming Deadlines | {{summary.deadlines}} |
| Notes | {{summary.notes}} |

## Critical First
> Acceptable Degradation / health reasons that must be cleared before other work. Document the Runbook step ID for each task.

- [ ] {{critical.items[0].description}} — Owner: {{critical.items[0].owner}} — Due: {{critical.items[0].due}} (`{{critical.items[0].runbook_ref}}`)
- [ ] {{critical.items[1].description}} — Owner: {{critical.items[1].owner}} — Due: {{critical.items[1].due}} (`{{critical.items[1].runbook_ref}}`)
- [ ] {{critical.items[2].description}} — Owner: {{critical.items[2].owner}} — Due: {{critical.items[2].due}} (`{{critical.items[2].runbook_ref}}`)

## Operational Tasks
| Task | Owner | Due | Est. Duration (min) | Last Recorded Worklog | Notes |
| --- | --- | --- | --- | --- | --- |
{{#operational.tasks}}
| {{task}} | {{owner}} | {{due}} | {{estimate_min}} | {{last_worklog}} | {{notes}} |
{{/operational.tasks}}

## Runbook Reviews
| Runbook ID | Status | Review Due (days) | Owner | Follow-up |
| --- | --- | --- | --- | --- |
{{#runbook_reviews}}
| {{runbook_id}} | {{status}} | {{review_due_in_days}} | {{owner}} | {{follow_up}} |
{{/runbook_reviews}}

## Validation Pending
| Playbook ID | Artifact | Owner | Due | Evidence Required |
| --- | --- | --- | --- | --- |
{{#validation_pending}}
| {{playbook_id}} | {{artifact}} | {{owner}} | {{due}} | {{evidence}} |
{{/validation_pending}}

## Distribution & Sign-off
- 保存先: `reports/ops/daily_agenda/{{agenda.date}}.md`
- JSONエクスポート: `reports/ops/daily_agenda/agenda_{{agenda.date}}.json`
- Runbook: [RUN-OPS-AGENDA-01](../runbooks/RUN-OPS-AGENDA-01.md)
- Validationログ連携: `reports/validation_log/AC-51_ops_{{agenda.date}}.md`
- Ops Worklog記録: `tradectl ops log add --task agenda_generation --duration {{agenda.duration_min}} --notes "RUN-OPS-AGENDA-01#signoff"`

> Codex/Opsは完了後に`reports/ops/daily_agenda/`へ証跡を保管し、`RUN-OPS-AGENDA-01`で承認手順を完了させること。
