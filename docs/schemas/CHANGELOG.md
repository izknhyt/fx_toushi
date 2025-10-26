# Schema Registry Change Log

## 2025-10-26
- Initial registry bootstrap with `accounts_profile.schema.json` (AccountAggregatorService, §51.1)
  and `order_state.schema.json` (OrderStateStore, §84.2). Enumerations for account `mode`, order
  `status`, and recovery `trigger_reason` were formalised per the detailed design. Runtime symlinks
  are available under `schema/` for validator integrations.
- Added validation test scaffold (`pytest -k json_schema_validation`) to enforce Draft 2020-12
  compliance for the new schemas.
