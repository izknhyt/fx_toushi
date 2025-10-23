<!-- 障害対応完了後24時間以内に作成するポストモーテムテンプレート。 -->
# Incident Report

- **Incident ID**: {{incident_id}}
- **Severity**: {{severity}} (`INFO|WARN|MAJOR|CRITICAL`)
- **Detected At (JST)**: {{detected_at}}
- **Resolved At (JST)**: {{resolved_at}}
- **Reporter**: {{reporter}}
- **Impacted Mode(s)**: {{impacted_modes}}
- **Impacted Symbols**: {{impacted_symbols}}
- **Related Runbooks**: {{runbook_refs}}

## Summary
- 発生概要: {{summary}}
- 現在の状態: {{current_state}}

## Impact Assessment
| Item | Detail |
| --- | --- |
| 影響範囲 | {{impact.scope}} |
| 影響時間 | {{impact.duration}} |
| エンドユーザー影響 | {{impact.end_user}} |
| 金額/リスク影響 | {{impact.financial}} |
| 運用対応負荷 | {{impact.ops_load}} |

## Timeline
| Timestamp (JST) | Actor | Action / Event | Evidence |
| --- | --- | --- | --- |
{{#timeline}}
| {{ts}} | {{actor}} | {{event}} | {{evidence}} |
{{/timeline}}

## Root Cause Analysis
- 直接原因: {{root_cause.immediate}}
- 真因分析 (Why x5): {{root_cause.five_whys}}
- 関連シグナル/ログ: {{root_cause.related_artifacts}}

## Mitigation & Recovery
- 暫定対応: {{mitigation.interim}}
- 恒久対策: {{mitigation.permanent}}
- Runbook更新要否: {{mitigation.runbook_update}}
- 監査ログ連携 (`logs/audit`): {{mitigation.audit_link}}

## Follow-up Actions
| Owner | Action Item | Due Date | Status |
| --- | --- | --- | --- |
{{#follow_ups}}
| {{owner}} | {{action}} | {{due_date}} | {{status}} |
{{/follow_ups}}

## Communications
- 初動通知: {{communications.initial}}
- エスカレーション: {{communications.escalation}}
- リリース/顧客告知: {{communications.external}}

## Attachments
- Incident Log: `logs/ops/incident_{{incident_id}}.md`
- Metrics Snapshot: {{attachments.metrics}}
- CLI Evidence: {{attachments.cli}}
- 追加資料: {{attachments.extra}}

## Approvals
| Role | Name / Initials | Timestamp (JST) | Notes |
| --- | --- | --- | --- |
| Ops Lead | {{approvals.ops_lead.name}} | {{approvals.ops_lead.timestamp}} | {{approvals.ops_lead.note}} |
| Product Owner | {{approvals.product_owner.name}} | {{approvals.product_owner.timestamp}} | {{approvals.product_owner.note}} |
| Risk Lead | {{approvals.risk_lead.name}} | {{approvals.risk_lead.timestamp}} | {{approvals.risk_lead.note}} |

> タイムライン・影響評価・承認欄はRunbook `RUN-INCIDENT-01`および詳細設計§7.5の運用フローに従って更新すること。
