# Schema Registry Change Log

## 2025-03-17
- Added `human_gate_config.schema.json` to capture Human Gate double-ack roles, comment thresholds,
  and Reduce-Only advisor weights per detailed design §3.5.6/§5.12. Updated `cfg.schema.json`
  so profile `gates` may override required roles and comment lengths for mode-specific workflows.

## 2025-03-16
- Added `ops_config.schema.json` to codify AutomationEffectTracker thresholds/notifications and
  `roles_config.schema.json` for CLI permission catalogues, aligning detailed design §52/§57/§68
  with the new `config/ops.yaml` / `config/roles.yaml` scaffolds. Config smoke tests now validate
  both scaffolds under `pytest -k config_schema_smoke`.

## 2025-03-15
- `gate_state.schema.json` を `market`/`risk`/`human` のネスト構造に更新し、ニュース/カレンダー/Spread/Reduce-Only/ダブルエントリー要件を個別プロパティへ分割。
  `required_roles`・`acknowledged_roles`・`comment_min_length` を追記し、`schema/gate_state.sample.json` を v2 レイアウトへ更新した。

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
