# Data Latency Tuning Evidence

| Date | Change | Command/Artifact | Owner | Notes |
| --- | --- | --- | --- | --- |
| 2025-03-21 | provider_profiles/local timeout bump (8→12s) | `vim config/provider_profiles/local.yaml` *(pending actual edit; tracked via RUN-DATA-05 profile section)* | Ops Manager | Template row created to document §11.1-4 closure. Real diff/hash to be added with next tuning cycle. |
| 2025-03-21 | Chunked resync plan | `tradectl resync --since 2025-03-10T00:00:00Z --chunk 6h --pause 30s` *(planned)* | Data Lead | Placeholder referencing new runbook section; actual chunk logs appended when CLI exposes option. |

- Linked Runbook: docs/runbooks/RUN-DATA-05.md (v1.5+ profile section).
- Review target: docs/risk_review/20250318_prelaunch.md §11.1-4.
