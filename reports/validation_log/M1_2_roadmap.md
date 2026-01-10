# M1.2 Roadmap

- generated_at: 2026-01-09T10:40:00Z
- scope: M1.2 prep for `reports.performance.enable` and `data.paid_feed`.
- status: complete (personal use; paid feed paper/live steps waived)

## Ordered Tasks

1. Performance snapshot pipeline (metrics + latest report).
   - Status: done (CLI added: `tradectl report performance` / `tradectl reports performance`).
   - Evidence: `metrics/performance_snapshot.jsonl`, `reports/performance/latest.md`,
     `reports/validation_log/evidence/20260109/report_performance.json`,
     `reports/validation_log/evidence/20260109/report_performance_run2.json`,
     `reports/validation_log/evidence/20260109/report_performance_run3.json`.

2. Performance enablement smoke (Backtest/Paper).
   - Status: done (paper evidence captured).
   - Required: set `defaults.<mode>.reports.performance.enable=true` and run
     `tradectl reports performance --profile <mode>` with evidence saved.
   - Required: 3 consecutive runs of `reports/performance/latest.md`.
   - Evidence: `reports/validation_log/evidence/20260109/report_performance_paper.json`,
     `reports/validation_log/evidence/20260109/performance_paper.md`.

3. Storage cost evaluation (AC-45).
   - Status: done (sizes + sharing recorded).
   - Required: summarize storage impact and share with ops_automation_writers.
   - Template: `reports/validation_log/AC-45_storage_cost_20260109.md`.

4. Paid feed simulator stub.
   - Status: done (stub created, provider wired, CLI test passes).
   - Evidence: `tools/paid_feed_stub.py`, `src/data/providers/paid_feed_stub.py`,
     `data/paid_feed_stub.csv`, `reports/validation_log/evidence/20260109/pytest_data_status_cli.log`.
   - Required: integrate into backtest/paper flow and validate with `pytest -k data_status_cli`.

5. Paid feed paper verification.
   - Status: waived (personal use).
   - Required: set `defaults.paper.data.paid_feed=true`, run `tradectl data status --profile paper`,
     and confirm SLA thresholds in `metrics/data_ingestion_sla.jsonl`.

6. Paid feed live gating and rollback rehearsal.
   - Status: waived (personal use).
   - Required: PO/Compliance double sign-off and rerun `RUN-DATA-05` + `RUN-DATA-06`.

## Notes

- Runbook: `docs/runbooks/RUN-FEATURE-FLAG-01.md` §§5.5–5.6.
- Paid feed paper/live steps waived because this installation is for personal use only.
- reports.performance.enable is kept disabled by default; enable only when running performance snapshots manually.
