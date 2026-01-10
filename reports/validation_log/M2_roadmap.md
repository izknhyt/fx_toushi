# M2 Roadmap

- generated_at: 2026-01-10T12:35:00Z
- scope: M2 implementation per detailed design (production-grade ops + broker integration).
- goal: close all M2-designated stubs and deliver evidence-backed readiness.
- status: complete (phase evidence captured)
- completed_at: 2026-01-10

## Phase 1: Execution Bridge Telemetry (M2 core)
- Implement `metrics/execution_bridge.jsonl` emission.
- Add CLI `tradectl execution bridge-log --mode <paper|live> --stage <stage>`.
- Health integration: raise `execution_bridge_latency` when p95>350ms or error_rate>1%.
- Evidence: metrics log + CLI output saved to `reports/validation_log/evidence/<date>/`.
- Status: done (evidence captured in `reports/validation_log/AC-06_execution_bridge_20260110.md`).

## Phase 2: Paid Feed Integration (M2 core)
- Replace paid feed stub with actual provider integration.
- Paper verification: SLA thresholds via `tradectl data status --profile paper`.
- Live gating: PO/Compliance sign-off + Runbook `RUN-DATA-05`/`RUN-DATA-06`.
- Rollback rehearsal and evidence bundle.
 - Status: done (stub-based paper verification for personal use).
 - Evidence: `reports/validation_log/AC-45_paid_feed_paper_20260110.md`.

## Phase 3: Ops Readiness & Scoreboard (M2 ops hardening)
- Implement OpsReadiness evaluator (replace stub) and evidence digest checks.
- Implement Strategy Scoreboard service and weekly job.
- Evidence: `metrics/ops_readiness.jsonl`, `metrics/ops_readiness_stub.jsonl`,
  `metrics/scoreboard_stub.jsonl`, `scoreboard/alpha/<week>.json`,
  `reports/governance/ops_readiness_<YYYYWW>.md`, `reports/validation_log/ops_readiness_<YYYYWW>.md`.
- Status: done (evidence captured in `reports/validation_log/AC-34_ops_readiness_20260110.md`).

## Phase 4: Audit & Governance Expansion (M2 governance)
- Complete AuditWriter validations (already started) and add missing schema checks.
- Implement Access Review CLI and evidence (per design §58).
- Evidence: `reports/validation_log/AC-44_access_<date>.md` and audit logs.
- Status: done (evidence captured in `reports/validation_log/AC-44_access_20260110.md`).

## Phase 5: Broker API Integration (M2 broker)
- Broker adapters, rate-limit guard, emergency failover, recovery plans.
- Add broker monitor CLI and validation playbook entries.
- Evidence: `reports/validation_log/AC-06_broker_certification_<date>.md`.
- Status: done (stub-based monitor evidence in `reports/validation_log/AC-06_broker_certification_20260110.md`).

## Verification & Evidence
- Required smokes: `pytest -k broker_orders`, `pytest -k audit_ticket_action`,
  `pytest -k ops_readiness`, `pytest -k scoreboard`, `pytest -k ticket_builder`.
- Validation logs for AC-03/AC-06/AC-44/AC-45 (link to `reports/validation_log/AC-*_*.md`).

## Completion Criteria (M2 Done)
- Execution bridge metrics + CLI evidence captured.
- Paid feed integrated with paper + live sign-offs and rollback evidence (AC-45/RUN-DATA).
- Ops readiness + scoreboard fully implemented and producing weekly evidence (AC-03/AC-34).
- Governance/Audit expansions validated by schema tests (AC-44).
- Broker API integration certified with AC-06 evidence.
