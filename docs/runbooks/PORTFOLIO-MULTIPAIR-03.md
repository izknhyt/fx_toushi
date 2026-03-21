# PORTFOLIO-MULTIPAIR-03

- Version: 0.1
- Last Updated: 2026-03-21
- Purpose: Review the next pair expansion only after the current pilot pair is stable.

## Preconditions

- `multi_pair_pilot_completion_gate_status=qualified_for_pair_expansion`
- `runtime_guardrail_status=ready`
- `rollout_suppression_status=inactive`
- `shadow_feedback_recovery_resolution_status=resolved`
- `active_discrepancy_count=0`

## Review Steps

1. Confirm the current pilot pair still satisfies the qualified completion gate.
2. Confirm suppression, rollback recovery, and runtime guardrails are all clear.
3. Review the next ranked pair candidate from the pair-expansion gate.
4. Start the next `multi_pair_preparation` packet for that symbol only.
5. Keep the newly added pair shadow-first until it reaches the same pilot completion gate.

## Primary Commands

- `tradectl portfolio pair-expansion`
- `tradectl portfolio next-stage --phase multi_pair_preparation --next-symbol <SYMBOL>`
- `tradectl portfolio next-stage --phase multi_pair_preparation --next-symbol <SYMBOL> --run`
