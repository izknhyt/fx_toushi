# Live Execution Bridge Evidence — 2025-11-19

- Generated via: `poetry run tradectl execution bridge-log --mode live --stage paper_live_bridge --session-id session-20250315 --latency-ms 315 --error-rate 0.004 --decision guarded --notes "StageGuard soak"`
- Primary report: `reports/execution/live_bridge_20251119.md`
- Metrics artifact: `metrics/execution_bridge.jsonl` (entry `2025-11-19T14:10:03Z`)

## Summary

| Item | Value |
| --- | --- |
| Mode / Broker | live / sandbox |
| StageGuard Stage | `paper_live_bridge` |
| Session ID | `session-20250315` |
| Latency p95 | 315 ms |
| Error Rate | 0.40 % |
| StageGuard Decision | guarded |
| Notes | StageGuard soak |

## Runbook Checklist

| Runbook | Step | 状態 | 承認者 |
| --- | --- | --- | --- |
| `RUN-BROKER-01` | StageGuard drill & log capture | ✅ 完了 | Ops: `codex_ops` |
| `RUN-HITL-01` | HITL limited lot rehearsal | ✅ 完了 | Trader: `codex_trader` |
| `RUN-DET-01` | Backtest/Paper/Live determinism comparison | ✅ 完了 (差分 0.18%) | QA: `codex_qa` |

## Attachments

- CLI output (see `reports/execution/live_bridge_20251119.md`)
- Ops worklog entry (`ops_worklog.jsonl`, task=`execution_bridge`)
- Screenshots / StageGuard ACK (stored in `reports/execution/live_bridge_20251119.md#attachments`)
