# COMPLIANCE-01: Risk Disclosure Consent Runbook

> Status: stub
> Owner: Compliance
> Review cycle: 90d
> Version: 0.2
> Last updated: 2026-01-12

## Purpose
- Collect and record risk disclosure consent.
- Provide evidence linkage for audit and ops review.

## Preconditions
- Approved disclosure document and hash available.
- Operator has compliance role.

## Procedure
1. Review disclosure document and version.
2. Capture consent via CLI (`tradectl compliance risk-disclosure enforce` or `tradectl compliance ack`).
3. Register device binding (`tradectl compliance device register`) when prompted.
4. Record `consent_reference_id` in evidence log.
5. Link evidence to validation playbook entry.

## Evidence
- logs/audit/risk_consent_<YYYYMMDD>.jsonl
- docs/validation_playbook/AC44_risk_consent.yaml

## Rollback
- If consent must be revoked, record a rejection and notify Ops.

## Change Log
- 2025-03-30: Stub created.
- 2026-01-12: Added device binding + validation playbook references.
