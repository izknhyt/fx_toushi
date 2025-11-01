<!-- 設計仕様に基づき、ドリル完了後に作成する標準レポート。 -->
# Drill Report

- **Drill Execution ID**: {{execution_id}}
- **Scenario ID**: {{scenario_id}}
- **Plan ID**: {{plan_id}}
- **Facilitator**: {{facilitator}}
- **Date (JST)**: {{date_jst}}
- **Related Runbooks**: {{runbook_refs}}

## Timeline
| Timestamp (JST) | Actor | Action / Event | Evidence |
| --- | --- | --- | --- |
{{#timeline}}
| {{ts}} | {{actor}} | {{event}} | {{evidence}} |
{{/timeline}}

## Runbook Step Review
| Step Ref | Expected Outcome | Actual Outcome | Notes |
| --- | --- | --- | --- |
{{#runbook_steps}}
| {{step_id}} | {{expected}} | {{actual}} | {{notes}} |
{{/runbook_steps}}

## SLA Recovery Determination
- 目標SLA復旧時間: {{sla.target}}
- 実測復旧時間: {{sla.actual}}
- 判定 (`MEETS|BREACH`): {{sla.decision}}
- 判定理由: {{sla.reason}}
- 関連Runbookチェック: {{sla.runbook_check}}

## Sign-off
| Role | Name / Initials | Timestamp (JST) | Status | Notes |
| --- | --- | --- | --- | --- |
{{#sign_offs}}
| {{role}} | {{name}} | {{timestamp}} | {{status}} | {{notes}} |
{{/sign_offs}}

## Follow-up Actions
| Owner | Action Item | Tracking Ticket | Due Date | Status |
| --- | --- | --- | --- | --- |
{{#follow_ups}}
| {{owner}} | {{action}} | {{ticket}} | {{due_date}} | {{status}} |
{{/follow_ups}}

> タイムライン、Runbookステップ検証、SLA判定、サインオフ、フォローアップは設計書§53.4および関連Runbook（例: `RUN-OPS-AGENDA-01`, `RUN-DATA-05`）に従って更新すること。
