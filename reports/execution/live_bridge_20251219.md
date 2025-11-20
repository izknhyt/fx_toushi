# Execution Bridge Evidence — 2025-12-19

- Generated At: 2025-12-19T14:05:00Z
- Mode: live
- Broker: sandbox
- StageGuard Stage: paper_live_bridge
- Session IDs: session-asia-03, session-london-04

## Metrics

- Latency p95 (ms): 282.0
- Error Rate: 0.20%
- Avg Slippage: 0.9 bps (`reports/performance/live_bridge_pnl_20251119-20251219.md`)

## StageGuard Exercise

- Decision: normal
- Spread Guard: inactive (`spread_cooldown=false`)
- Notes: Month-long soak complete, reduce-only triggers none.

## Actions

- Attach this report and `reports/performance/live_bridge_pnl_20251119-20251219.md` to `RUN-HITL-01` evidence.
- Update `ops_worklog` (`task=execution_bridge`) with latency/error metrics.
- Feed stats into `metrics/execution_bridge.jsonl` via `tradectl execution bridge-log`.
