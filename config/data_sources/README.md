# Data Sources

Templates for provider connection metadata referenced by the detailed design.

Each file should validate against `schema/data_source.schema.json` and include
rate limits, backfill limits, and endpoint metadata. M1 defaults keep external
credentials out of repo; use local overrides or secrets for runtime values.
