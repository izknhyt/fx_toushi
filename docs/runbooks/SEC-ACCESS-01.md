# SEC-ACCESS-01: Access Governance Review

> **AC Coverage**: AC44_access  
> **Runbook Version**: v0.1  
> **Last Updated (UTC)**: 2026-01-19  
> **Owner**: Codex (Ops proxy)

## Purpose
- Standardize access governance reviews for principals/devices.
- Ensure evidence and validation playbook entries are captured.

## Scope / Trigger
- Quarterly access review or ad-hoc security audit.

## Procedure
1. Verify role catalog and admin roster in `config/roles.yaml`.
2. List principals and devices:
   - `tradectl access principals list --json`
   - `tradectl access devices list --json`
3. Start a review:
   - `tradectl access review start --scope quarterly --due YYYY-MM-DD --actor <admin_id> --json`
4. Complete the review with findings/actions and evidence:
   - `tradectl access review complete --review <id> --finding CODE:severity:note --action ACTION_ID:owner:status --evidence <path> --actor <admin_id> --json`
5. Confirm validation playbook entry exists in `docs/validation_playbook/AC44_access.yaml`.
6. Generate the access report for the quarter:
   - `tradectl access report --profile compliance --format md`

## Checklist
- [ ] Findings/actions captured with evidence path.
- [ ] Validation playbook entry appended.
- [ ] Report stored under `reports/governance/access/`.

## Escalation
- Overdue reviews must be surfaced in Ops Agenda and escalated to the Ops Lead.

## Change Log
- Update `reports/governance/runbook_changelog.md` on runbook edits.
