# Schema Registry Change Log

## 2025-03-14
- Added configuration schema set for Codex scaffolds: `strategy_manifest`, `feature_pipeline`,
  `board_modes`, `cfg`, `sla_threshold_profile`, and the operational `gate_state` snapshot. These
  contracts align detailed design §4.4/§0.6.9 with RUN-DATA-05, RUN-SPREAD-03, RUN-RISK-01, and
  STRAT-PROMOTE-01. Validation coverage is provided via `pytest -k config_schema_smoke` against the
  config scaffolds and `schema/gate_state.sample.json`.

## 2025-10-26
- Initial registry bootstrap with `accounts_profile.schema.json` (AccountAggregatorService, §51.1)
  and `order_state.schema.json` (OrderStateStore, §84.2). Enumerations for account `mode`, order
  `status`, and recovery `trigger_reason` were formalised per the detailed design. Runtime symlinks
  are available under `schema/` for validator integrations.
- Added validation test scaffold (`pytest -k json_schema_validation`) to enforce Draft 2020-12
  compliance for the new schemas.
