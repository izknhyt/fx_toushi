# PORTFOLIO-SHADOW-ROLLBACK-01

- Version: `0.1`
- Last Updated: `2026-03-21`
- Owner: `Codex / Portfolio OS`

## Purpose
Execute the rollback and recovery workflow when rollout drift persists and the shadow system recommends baseline rollback or manual runtime-guardrail clearance.

## Preconditions
- A daily shadow ops summary exists and includes `rollout_rollback_recommended=true` or `runtime_guardrail_manual_clear_required=true`.
- The latest focused validation result and rollout execution state are available.
- Runtime guardrails remain blocked until this checklist is complete.

## Command
```bash
tradectl portfolio shadow-feedback-recover --run
```

## Recovery Checklist
1. Keep rollout freeze active and do not resume next-stage automation.
2. Confirm the baseline allocation profile remains `portfolio_admission_v2` and disable shadow feedback allocation overrides.
3. Review open discrepancies and ensure no new rollout execution is started while mismatch remains unresolved.
4. Re-run focused validation and compare the latest `adopt / hold / reject` result against actual rollout state.
5. Only after the mismatch is cleared and open discrepancies are resolved, manually clear the runtime guardrail and resume rollout.

## Clear Conditions
- `rollout_guardrail_status = monitor`
- `runtime_guardrail_manual_clear_required = false`
- `shadow_feedback_rollout_alignment_status != mismatch`
- `active_discrepancy_count = 0`
- a fresh focused validation artifact exists

## Follow-up
- Record the generated recovery packet artifact in [docs/development_plan.md](/Users/izumimotohayato/development/codex_invest/docs/development_plan.md) if this runbook is used during development.
- If recovery is executed, keep the recovery ledger under `logs/ops/shadow_feedback_recovery.jsonl` available for the next daily ops review.
