# M1.1 Progress Summary

- generated_at: 2025-12-24T11:38:25Z

## Completed

- RateLimitGuard stage decisions can be auto-applied with CLI logging (`data status --auto-apply`).
- Acceptable Degradation suggestion pipeline writes HealthState + evidence (`data status --suggest-guarded`).
- Risk disclosure enforcement blocks ticket actions when consent is pending.
- Reduce-only advisor stub wiring adds advisory badge + checklist hook (flagged by `reduce_only_advisor`).
- Weekly report extended blocks template is available behind `reporter.enable_extended_blocks`.

## Evidence

- `metrics/rate_limit_window.jsonl` (decision_source/runbook_ref entries)
- `logs/ops/stage_change.log` (auto-apply changes)
- `logs/events/health_suggested.jsonl` (guarded suggestions)
- `snapshots/latest/health_state.json` (HealthState snapshot)
- `src/ticket/builder.py` (advisor metadata + badge/checklist hook)
- `src/reporter/templates/weekly_m1_core_extended.md` (extended weekly report template)

## Notes

- Risk disclosure enforcement is gated by `TRADECTL_RISK_DISCLOSURE_ENFORCE=1` or `TRADECTL_PROFILE=<mode>` defaults in `config/feature_flags.yaml`.
