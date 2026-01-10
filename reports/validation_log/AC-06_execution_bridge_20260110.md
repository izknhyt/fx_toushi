# AC-06 Execution Bridge Telemetry Validation (2026-01-10)

## Scope
- M2 Phase 1 execution bridge telemetry + CLI evidence.
- Runbook reference: RUN-BROKER-01 (bridge latency drill).

## Evidence
| Artifact | SHA256 |
| --- | --- |
| src/execution/bridge.py | 7e0f2c1ae53319a32ec8a02ddac759bc759231349aeceddb3f2d98ad517dd478 |
| metrics/execution_bridge.jsonl | 0a1cac2f2e36ef8cc8c52bb8c75e727eb0ab77fb12807c5f176aaeccda9027ea |
| reports/execution/live_bridge_20260110.md | b14ab229943f91f9a7ab712aec381a58dc3e999f8f24b8d4998071ddd8c2b5d3 |
| ops_worklog.jsonl | a1c620fbf26a12d3dd471e3f567fd4192fcc25a6314165f150cba8e4031678da |
| reports/validation_log/evidence/20260110/execution_bridge_log.json | f5b39ad79ede32ad35f7b59f637afaf131e6be99526aaa29fe983c17cb838e2a |

## Notes
- CLI: `tradectl execution bridge-log --mode paper --broker sandbox --stage paper_live_bridge`.
- Thresholds used: latency_ms>350 or error_rate>1% triggers warn + ops_worklog entry.

## Sign-off
- Ops: hayato 2026-01-10
- Risk: hayato 2026-01-10
- PO: hayato 2026-01-10
