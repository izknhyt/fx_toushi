# M1–M1.2 Gap List (Detailed Design v1.37)

This table tracks gaps between the detailed design and current implementation
for the M1–M1.2 milestones. Use it to pick the next batch of work.

Legend:
- Status: missing / partial / done
- Priority: P0 (blocker), P1 (next), P2 (later)

| ID | Milestone | Design Ref | Requirement | Current State | Gap | Priority | Suggested Next Step |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G-01 | M1 Core | §89.1, §2.3, §3.15 | Resync orchestration: enqueue, pause signal flow, trigger backfill pipeline, emit ResyncCompleted chain | Resync queue + `ResyncCoordinator` drains jobs; `SessionManager.catch_up` toggles `catch_up_state` | None (M1 scope) | P0 | Done |
| G-02 | M1 Core | §3.1, §89.1, §1636 | `DataIngestionService.backfill` real fetch + 6h chunking + retry + manual CSV fallback | Backfill uses provider handlers, chunking, retries, SLA logs | None (M1 scope) | P0 | Done |
| G-03 | M1 Core | §3.15 | Resync latency metrics + resync lag health raise | Resync latency metrics logged; resync lag health raise; SnapshotManager data mismatch event logged | None (M1 scope) | P1 | Done |
| G-04 | M1 Core | §3.1 (1588), §89 | Fetch/processing delay separation in pipeline | BufferCoordinator queue timestamps applied to fetch/processing delays | None (M1 scope) | P1 | Done |
| G-05 | M1 Core | §90.3 | NTP drift + news calendar integration into Spread Guard | Spread monitor enriches NTP drift + calendar event hints; CLI writes cooldown_eta | None (M1 scope) | P1 | Done |
| G-06 | M1.1 | §2567, RUN-FEATURE-FLAG-01 §5.2 | Reduce-Only Advisor real evaluation + audit fields | Reduce-Only advisor checks spread/latency/slippage/kill switch | None (M1 scope) | P1 | Done |
| G-07 | M1.1 | §2897, §2925 | Risk disclosure enforcement (block high-risk ops) + consent telemetry | Enforcement path present; metrics log added | None (M1 scope) | P1 | Done |
| G-08 | M1.1 | §2640 | Reporter extended blocks populate actual summaries | Extended blocks load kill switch/spread/data quality/resync/manual CSV summaries | None (M1 scope) | P1 | Done |
| G-09 | M1.1 | §3491 | `tradectl config validate` CLI | CLI wrapper added, writes `reports/validation_log/config_<date>.md` | None (M1 scope) | P2 | Done |
| G-10 | M1.2 | §1.10, RUN-FEATURE-FLAG-01 §5.5 | Performance Snapshot flag gating + auto report integration | Feature flag gate added; weekly report auto-includes snapshot when enabled | None (M1 scope) | P1 | Done |
| G-11 | M1.2 | §49–§50 | Paid feed evaluation + licensing governance integration | Capability registry + evaluator + data status integration added | None (M1 scope) | P1 | Done |

Notes:
- Additional M1.1 Hardening items (audit bundle, release gate, ops drill orchestrator) are not listed here yet; add if you want to pursue the full hardening scope.
