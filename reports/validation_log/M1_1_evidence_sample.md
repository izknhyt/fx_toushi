# M1.1 Evidence Sample

- generated_at: 2025-12-24T11:12:00Z

## Evidence
- `metrics/rate_limit_window.jsonl` (decision_source/runbook_ref entries)
- `logs/ops/stage_change.log` (auto apply)
- `logs/events/health_suggested.jsonl` (guarded suggestion)
- `snapshots/latest/health_state.json` (HealthState snapshot)
- `logs/audit/compliance.jsonl` (risk disclosure consent audit)

## Notes
- Generated with `tradectl data status --log-stage-eval --auto-apply --suggest-guarded` and `tradectl compliance ack`.
