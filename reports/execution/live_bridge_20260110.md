# Execution Bridge Evidence — 2026-01-10

- Generated At: 2026-01-10T11:49:43Z
- Mode: paper
- Broker: sandbox
- StageGuard Stage: paper_live_bridge
- Session ID: session-bridge-001

## Metrics

- Latency p95 (ms): 420.0
- Error Rate: 2.00%

## StageGuard Exercise

- Decision: guarded
- Notes: M2 execution bridge telemetry

## Actions

- Capture CLI logs and attach to RUN-BROKER-01 evidence bundle.
- Update ops_worklog task `profit_readiness` if latency > 350ms or error_rate > 1%.
