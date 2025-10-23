<!-- 危険キーを含む設定変更を実施する際の計画テンプレート。 -->
# Configuration Change Plan

- **Change ID**: {{change_id}}
- **Requested By**: {{requested_by}}
- **Date (JST)**: {{date_jst}}
- **Target Profile(s)**: {{target_profiles}}
- **Affected Files**: {{affected_files}}
- **Feature Flags**: {{feature_flags}}
- **Related Runbooks**: {{runbook_refs}}

## Summary
- 変更目的: {{summary.purpose}}
- 背景/KPI: {{summary.kpi_context}}
- 期待される結果: {{summary.expected_outcome}}

## Scope & Impact Assessment
| Category | Detail |
| --- | --- |
| 影響範囲 (Mode/サービス) | {{impact.scope}} |
| 危険キー | {{impact.dangerous_keys}} |
| リスク評価 (Kill Switch/Spread) | {{impact.risk_assessment}} |
| 運用影響 (Runbook/手順) | {{impact.operational}} |
| ロールバック条件 | {{impact.rollback_conditions}} |

## Implementation Plan
1. バックアップ取得: {{plan.backup}}
2. 検証環境でのテスト: {{plan.testing}}
3. 本番適用手順 (`tradectl cfg apply` 等): {{plan.apply_steps}}
4. モニタリング/検証 (`metrics`, `logs`) : {{plan.monitoring}}
5. ロールバック手順: {{plan.rollback}}

## Timeline
| Step | Owner | Scheduled Time (JST) | Completed |
| --- | --- | --- | --- |
{{#timeline}}
| {{step}} | {{owner}} | {{scheduled_time}} | {{completed}} |
{{/timeline}}

## Validation Checklist
- [ ] `tradectl cfg diff` 実行結果を添付 (`cfg_hash`: {{validation.cfg_hash}})
- [ ] `poetry run pytest -k config_guard` 実行
- [ ] Runbook更新・通知完了: {{validation.runbook_updates}}
- [ ] 監査ログ (`AuditWriter`) 連携確認: {{validation.audit_log}}

## Attachments
- Config Diff: {{attachments.diff}}
- テスト結果: {{attachments.test_log}}
- 監査イベント: {{attachments.audit_event}}

## Approvals
| Role | Name / Initials | Timestamp (JST) | Notes |
| --- | --- | --- | --- |
| Requester | {{approvals.requester.name}} | {{approvals.requester.timestamp}} | {{approvals.requester.note}} |
| Ops Lead | {{approvals.ops_lead.name}} | {{approvals.ops_lead.timestamp}} | {{approvals.ops_lead.note}} |
| Product Owner | {{approvals.product_owner.name}} | {{approvals.product_owner.timestamp}} | {{approvals.product_owner.note}} |
| Risk Lead | {{approvals.risk_lead.name}} | {{approvals.risk_lead.timestamp}} | {{approvals.risk_lead.note}} |

> 承認欄は詳細設計§3.19および§6.7のConfig Governance手順に従い、適用前に全員のサインを取得すること。
