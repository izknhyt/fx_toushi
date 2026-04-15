# Execution Bridge Evidence — 2025-11-19

- Generated At: 2025-11-19T14:10:03Z
- Mode: live
- Broker: sandbox
- StageGuard Stage: paper_live_bridge
- Session ID: session-20250315

## Metrics

- Latency p95 (ms): 315.0
- Error Rate: 0.40%

## StageGuard Exercise

- Decision: guarded
- Notes: StageGuard soak

## Actions

- Capture CLI logs and attach to RUN-BROKER-01 evidence bundle.
- Update ops_worklog task `profit_readiness` if latency > 350ms or error_rate > 1%.
