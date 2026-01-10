# M1.3 Roadmap (Guardrails Hardening)

- generated_at: 2026-01-09T12:25:00Z
- scope: Align guardrails schema/output/reporting with detailed design (EP03/EP04).
- status: complete (AC-03/AC-34 evidence captured)

## Phase 1: Schema Canonicalization
- Update `schema/guardrails_metrics.schema.json` to match detailed design.
- Make `risk_disclosure` and `auto_execute_forced_off` consistent with board/status/ticket outputs.
- Decide required vs optional fields for `reason`/`reasons`/`suggested_action`/`ack_user`/`exit_code`.

## Phase 2: Guardrails Output Alignment
- Ensure `metrics/guardrails.jsonl` uses canonical keys.
- Align `board/status/ticket.action.v2` field names with the schema.
- Target files (design references): `src/interfaces/cli/status.py`, `src/interfaces/cli/board.py`,
  `src/persistence/audit.py`, `src/ticket/builder.py`, `src/ticket/models.py`.
- Add or reconcile `auto_execute_forced_off` emission in guardrails events.

## Phase 3: Reporter Integration
- Ensure weekly report uses the canonical guardrails keys/order.
- Surface `risk_disclosure`/`auto_execute_forced_off` in summaries.
- Link guardrails evidence in `reports/validation_log/AC-*`.

## Phase 4: Verification & Evidence
- Run required smokes (per design): `pytest -k profit_readiness_smoke`,
  `pytest -k guardrails_latency_fallback`, `pytest -k risk_manager`,
  `pytest -k ticket_builder`, `pytest -k audit_ticket`.
- Capture evidence logs under `reports/validation_log/evidence/<date>/`.
- Update a validation log entry with hashes and links (AC-03 / AC-34).
- Evidence: `reports/validation_log/AC-03_guardrails_20260110.md`.

## Completion Criteria
- Schema matches detailed design and is referenced as the single source of truth.
- Guardrails metrics output conforms to schema (CI/spot-check).
- Report output aligns with canonical keys and order.
- Evidence is saved and linked (AC-03 / AC-34).
