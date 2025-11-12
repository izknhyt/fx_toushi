# PKG-JSON-SCHEMA Validation — 2025-03-19

| Command | Result | Notes |
| --- | --- | --- |
| `pytest tests/jsonschema -k json_schema_validation` | ✅ 40 passed (0.35s) | Full domain + integrity sweep using `referencing` registry (logs: `reports/implementation/20250315_pkg-json-schema-01/logs/pytest_json_schema_validation.log`). |
| `poetry run schema-validate config/profiles/backtest.yaml --schema docs/schemas/cfg.schema.json` | ✅ schema-validate CLI | Demonstrates new registry wiring for Ops CLI (output saved under `reports/implementation/20250315_pkg-json-schema-01/cli/schema_validate_profile_backtest_20250322.log`). |

## Highlights
- Tests & CLI now share `src/core/schema_registry.py`, eliminating RefResolver deprecation warnings.
- Sample payload from `docs/schemas/examples/performance_snapshot.sample.json` validated to ensure example files stay current.
- Feature Flag Register updated with rollback guidance (`jsonschema_referencing_registry`).

## Sign-off
- Ops Manager (prep): 2025-03-19T12:00+09:00
