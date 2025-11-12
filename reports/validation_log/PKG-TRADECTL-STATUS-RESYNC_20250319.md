# PKG-TRADECTL-STATUS-RESYNC Validation — 2025-03-19

| Command | Result | Notes |
| --- | --- | --- |
| `pytest tests/unit/test_cli_status.py tests/unit/test_cli_resync.py` | ✅ 6 passed (1.48s) | Verifies Acceptable Degradation banner metadata, Reduce-Only handling, snapshot diagnostics, ops action requests, and resync success/unimplemented/error paths. |
| `poetry run python -m tradectl status --json` | ✅ status_snapshot_20250322.json | Captured baseline banner/actions snapshot under `reports/implementation/20250322_pkg-tradectl-status-resync-01/metrics/`. |
| `poetry run python -m tradectl resync --json` | ✅ resync_20250322.json | Archived unavailable-path payload + log for auditing under `reports/implementation/20250322_pkg-tradectl-status-resync-01/cli/` and `logs/`. |

## Context
- Runbook references updated: `docs/runbooks/RUN-DATA-05.md` (v1.5)・`docs/runbooks/RUN-DATA-06.md` (v1.3) now embed CLI samples.
- Design §17.3/§17.4 refreshed with JSON output snippets.

## Sign-off
- Ops Manager (prep): 2025-03-19T12:05+09:00
