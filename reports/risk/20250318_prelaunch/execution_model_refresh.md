# Execution Model Refresh Evidence Log

| Date (JST) | Window | CLI Output | Hash Entry | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
| 2025-03-21 | last 14d | `tradectl execution export-live-fills --window 14d --out reports/performance/live_fill_stats_20250321.parquet` *(scheduled)* | `python tools/check_dataset_hash.py --manifest reports/data_manifest.json --strategy m1_baseline_ma_rsi --label live_fill_snapshot_20250321` *(template ready)* | Quant Lead / Ops Manager | Template entry created after RUN-EXEC-02 v1.1 update. Actual CLI output will be appended once live fills export CLI lands (ref: AC-43). |

- Ops Worklog ref: `tradectl ops workload log --task execution_model_refresh --note "window=14d"` (ID placeholder: `OW-20250321-EM01`).
- Linked Runbook: docs/runbooks/RUN-EXEC-02.md (v1.1)。
- Validation Log: reports/validation_log/execution_recalibration_20250321.md (pending if drift > 5%).
