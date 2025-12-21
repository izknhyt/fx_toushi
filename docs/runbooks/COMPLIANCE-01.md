# COMPLIANCE-01: Risk Disclosure Consent Runbook

> Status: stub
> Owner: Compliance
> Review cycle: 90d

## Purpose
- Collect and record risk disclosure consent.
- Provide evidence linkage for audit and ops review.

## Preconditions
- Approved disclosure document and hash available.
- Operator has compliance role.

## Procedure
1. Review disclosure document and version.
2. Capture consent via CLI (`tradectl compliance risk-disclosure accept`).
3. Record `consent_reference_id` in evidence log.
4. Link evidence to validation playbook entry.

## Evidence
- logs/audit/risk_consent_<YYYYMMDD>.jsonl
- reports/validation_log/AC-xx_risk_disclosure_<date>.md

## Rollback
- If consent must be revoked, record a rejection and notify Ops.

## Change Log
- 2025-03-30: Stub created.
