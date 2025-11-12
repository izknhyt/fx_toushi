# PKG-CONFIG-SCHEMA Validation — 2025-03-19

| Command | Result | Notes |
| --- | --- | --- |
| `pytest tests/config/test_config_schema_smoke.py -k config_schema_smoke` | ✅ 16 passed (0.81s) | Validated board_modes / feature_flags / feature_pipeline / risk_* / ops / scoring / scoreboard / profiles / SLA thresholds against their JSON Schemas. |
| `poetry run schema-validate config --schema docs/schemas/config_bundle.schema.json` | ✅ Exit 0 | Full bundle validation across `config/` succeeded (warning about entry-point install noted). |

> `pytest -k config_schema_smoke` currently triggers a pytest bug (Signal 11) on the sandboxed macOS runner. Running the explicit test module covers the same cases; the failure and workaround are documented here until the upstream issue is resolved.

## References
- Implementation packet: `docs/implementation_packets/20250315_config_schema_smoke.md`
- Evidence bundle: `reports/validation_log/PKG-CONFIG-SCHEMA_20250319.md` (this file)
- Runbooks touched: `docs/runbooks/CONFIG-SCAFF-01.md`, `docs/runbooks/daily_agenda/2025-03-18.md`

## Sign-off
- Ops Manager (prep): 2025-03-19T11:40+09:00
