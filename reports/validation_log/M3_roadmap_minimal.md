# M3 Roadmap (Minimal)

- generated_at: 2026-01-10T12:45:00Z
- scope: Minimal M3 scope for personal use (avoid full live broker automation).
- goal: only the minimum broker integration needed for manual/live verification.
- status: complete (evidence captured)

## Phase 1: Broker Connection Baseline
- Define broker adapter interface and minimal connection health checks.
- CLI: `tradectl broker monitor status` should surface adapter health.
- Evidence: `metrics/broker_api.jsonl`, `reports/ops/broker_monitor_<date>.md`.
 - Status: done (see M2 Phase 5 evidence).

## Phase 2: Manual Order Path (HITL)
- Implement manual order submission (no auto-execute).
- Ensure Kill Switch prevents submission when `state != none`.
- Target: `src/interfaces/cli/broker.py` + `tradectl broker order submit` (HITL-only).
- Evidence: `logs/audit/kill_switch_*.jsonl`, `ops_worklog.jsonl`,
  `reports/validation_log/AC-06_broker_certification_<date>.md`.
 - Status: done (see `reports/validation_log/AC-06_broker_orders_20260110.md`).

## Phase 3: Emergency Stop & Rollback
- Add emergency stop flow that logs to `ops_worklog.jsonl`.
- Provide rollback runbook evidence (manual checklist only).
- Runbook: `RUN-EMER-UNWIND-01`.
- Evidence: `reports/audit/manual_unwind_<date>.md`, `ops_worklog.jsonl`.
 - Status: done (see `reports/validation_log/AC-06_broker_orders_20260110.md`).

## Verification
- Run limited tests: `pytest -k broker_orders`, `pytest -k audit_ticket_action`.
- If `broker_orders` tests are absent, log the absence in evidence notes.

## Completion Criteria (M3 Minimal Done)
- Broker connection health check works and logs evidence.
- Manual order path respects Kill Switch.
- Emergency stop flow evidence captured.
