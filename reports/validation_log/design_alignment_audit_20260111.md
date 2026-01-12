# Design Alignment Audit (Backlog vs Implementation)

- generated_at: 2026-01-11T13:44:02Z
- backlog: docs/design_alignment_backlog.md
- status_counts: {'in_progress': 6, 'done': 38, 'todo': 130}

## Audit Scope
- Verified all backlog rows for referenced file existence (paths in notes).
- Checked for known evidence artifacts and CLI wiring gaps mentioned in the design doc.

## Mismatches / Gaps

| Item | Evidence | Impact | Suggested Backlog Action |
| --- | --- | --- | --- |
| Metrics artifacts missing | metrics/feature_cache.jsonl, metrics/replay_jobs.jsonl not found | Evidence required by completion definition | Mark affected EP-02 rows as in_progress or add evidence capture note |
| Resync ops evidence | reports/ops/resync/20251207T123315.611942Z.md... | Evidence present | N/A |
| `tradectl resync` wiring | CLI calls `resync()` without `session=` injection | Catch-up uses stub path in CLI | Note stub status in EP01-P3/EP-01 or defer until wiring is added |
| Guardrails tests evidence | `reports/validation_log/AC-03_guardrails_20260110.md` notes tests collected none for smoke patterns | Evidence incomplete for required smokes | Add test evidence or flag EP-03 for follow-up |

## Missing Paths (Referenced by Backlog)
- EP-02 Strategy Determinism (in_progress) [0.6.3 実装優先度マトリクス（M1）]: metrics/replay_jobs.jsonl
- EP02-P3 (in_progress) [91.7 Codex Packet & テスト計画（EP02-P1/P2/P3）]: metrics/replay_jobs.jsonl
- EP02-T1 (in_progress) [15.2 EP-02 Strategy Determinism（シグナル決定論）]: metrics/feature_cache.jsonl

## Notes
- Some evidence artifacts (metrics/logs) are runtime outputs; missing files indicate evidence not captured in this repo snapshot.
- Backlog entries may still be valid for M1 if stubs are explicitly accepted; this audit flags mismatches against the completion definition.
