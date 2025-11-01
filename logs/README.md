# Operations and audit logs

This directory holds the operational log streams that the detailed design binds to on-disk files. The
folders are created in-repo so first-run environments do not fail when the runtime attempts to append
new entries.

## File inventory and policies

| Path | Purpose | Retention & handling |
| --- | --- | --- |
| `logs/ops/review.log` | Captures escalations and follow-up items from weekly/quarterly ops reviews and incident post-mortems so that AC-45/AC-51 evidence links can be traced from the runbooks and review register.【F:detailed_design_fx_signal_tool_v1.md†L70-L79】【F:detailed_design_fx_signal_tool_v1.md†L1069-L1076】 | Retain locally for at least 12 months and archive quarterly alongside other audit logs per the ArchivePlanner policy.【F:detailed_design_fx_signal_tool_v1.md†L5388-L5405】 |
| `logs/ops/drill_plan.jsonl` | JSONL ledger of scheduled drill plans produced by `OpsDrillService.schedule`, feeding Ops Agenda capacity checks and audit hooks for drill readiness.【F:detailed_design_fx_signal_tool_v1.md†L6349-L6357】 | Keep a rolling history of at least four quarters so Ops Readiness sampling can correlate plans with executed evidence; archive with the matching drill reports when closing the audit window.【F:detailed_design_fx_signal_tool_v1.md†L2873-L2876】【F:detailed_design_fx_signal_tool_v1.md†L6356-L6360】 |
| `logs/ops/drill_execution.jsonl` | Execution timeline emitted while drills are running; paired with Markdown reports and evidence bundles for audit trails.【F:detailed_design_fx_signal_tool_v1.md†L6356-L6360】 | Same policy as the plan log—retain for four quarters and archive together with `reports/drill/` artifacts once compliance review is signed off.【F:detailed_design_fx_signal_tool_v1.md†L2873-L2876】 |

### Directory structure

Runtime components will create additional subdirectories (for example `logs/events/` or
`logs/ops/incident_*.md`) as features graduate from the scaffold. Those paths follow the same
retention strategy described in the ArchivePlanner section of the detailed design and should stay in
Git via `.gitkeep` files until the corresponding services populate them.【F:detailed_design_fx_signal_tool_v1.md†L5388-L5405】
