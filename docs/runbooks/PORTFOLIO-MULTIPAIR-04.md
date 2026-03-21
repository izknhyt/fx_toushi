# PORTFOLIO-MULTIPAIR-04

- Status: draft
- Owner: Codex / personal-use ops
- Purpose: Execute and review the next pair expansion rollout after the pair expansion gate is ready.

## Preconditions

- `multi_pair_expansion_gate_status=ready_for_pair_expansion`
- `rollout_suppression_status=inactive`
- `runtime_guardrail_status=ready`
- `shadow_feedback_recovery_resolution_status in {resolved, not_required}`

## Primary Commands

1. Render or execute the expansion rollout packet.

```bash
tradectl portfolio pair-expansion-rollout --current-symbol EURUSD --next-symbol GBPUSD
tradectl portfolio pair-expansion-rollout --current-symbol EURUSD --next-symbol GBPUSD --run
```

2. Review the resulting daily ops surface.

```bash
tradectl ops shadow-next-stage --run
```

## Review Checklist

1. Confirm the current active pilot pair is still stable and still qualifies for expansion.
2. Run the expansion rollout packet for the next pair only once per review cycle.
3. Review validation deltas and decision status from the latest expansion rollout artifact.
4. If suppression, recovery, or runtime guardrails re-open, stop rollout and return to the pair expansion gate.

## Evidence

- `reports/analysis/shadow/shadow_multi_pair_expansion_rollout_*.json`
- `reports/analysis/shadow/shadow_multi_pair_expansion_rollout_*.md`
- `reports/analysis/shadow/daily_shadow_ops_summary_*.json`
