<!-- Incident postmortem template (see design §63.1). -->
# Incident Postmortem

- **Incident ID**: {{incident_id}}
- **Category**: {{category}}
- **Severity**: {{severity}}
- **Status**: {{status}}
- **Opened At**: {{opened_at}}
- **Closed At**: {{closed_at}}
- **Board Mode**: {{board_mode}}
- **Health State**: {{health_state}}

## Summary
- 概要:
- 影響範囲:
- 主要判断:

## Timeline
| Timestamp | Runbook | Note | Evidence |
| --- | --- | --- | --- |
{{#timeline}}
| {{ts}} | {{runbook_ref}} | {{note}} | {{evidence}} |
{{/timeline}}

## Root Cause
- 原因:
- 再発条件:

## Corrective Actions
| Task ID | Description | Owner | Due | Status |
| --- | --- | --- | --- | --- |
{{#follow_ups}}
| {{task_id}} | {{description}} | {{owner}} | {{due}} | {{status}} |
{{/follow_ups}}

## Validation Links
- `validation_playbook/AC43_postmortem.yaml` 更新状況:
- Evidence:

## Runbook Updates
- 更新したRunbook:
- 変更理由:

## Closure Verification
- Verified By: {{verified_by}}
- Verification Note: {{verification_note}}
