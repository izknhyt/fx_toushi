# Schema Registry Change Log

## 2025-03-21
- Added `performance_snapshot.schema.json` capturing KPI snapshots (Sharpe, Sortino, drawdown, win rate, P&L metadata and governance state) for backtest/paper/live windows per detailed design §3.5.2/§7.6. Included curated sample `docs/schemas/examples/performance_snapshot.sample.json`, symlink `schema/performance_snapshot.schema.json`, and regression coverage via `tests/contracts/test_performance_snapshot_schema.py`.

## 2025-03-20
- Added `scoring_config.schema.json`, `scoreboard.schema.json`, and `risk_live_guard.schema.json` to codify scoring drift guards, governance thresholds, and Live Guard notification rules per detailed design §4.4.3〜§4.4.5. Config smoke tests now assert these scaffolds via `pytest -k config_schema_smoke`.
- Added `ops_readiness.schema.json` and `config_bundle.schema.json` so Ops Readiness reviews and the repository-wide bundle check (`poetry run schema-validate config --schema docs/schemas/config_bundle.schema.json`) align with RUN-OPS-AGENDA-01 / OPS-READINESS-01 workflows.
- Added `risk_policy.schema.json` to formalise risk policy profiles, kill switch thresholds, and reporting guardrails referenced in §5.2. The schema underpins `config/risk_policy.yaml` in the bundle validator.

## 2025-03-19
- Added `event_resync_completed.schema.json` capturing the resync.completed domain event (SessionManager.catch_up) per detailed design §16.1/§16.2, including context hashes for downstream replay validation.
- Added `audit_ticket_action.schema.json` to formalise ticket.action audit records with SpreadState snapshots and consent delta metadata as required by detailed design §3.6/§3.20/§16.3.
- Added `metrics_pipeline.schema.json` defining the `pipeline_step_elapsed_ms` metrics contract with board_mode labels per detailed design §16.4 and CLI `tradectl metrics report --validate`.
- Added `risk_disclosure_state.schema.json` documenting the compliance consent state structure (status, grace window, device binding) for `tradectl compliance status` validation per detailed design §3.30.

## 2025-03-18
- Added `mode_context.schema.json` capturing ModeContext composite structures (ModeProfile, MarketClock,
  DataFeedBundle, ExecutionProfile, AccountGateway, AuditChannel, SessionState/Handle, BackfillJob) per
  detailed design §3.1.0/§4.2.5. Startup validation templates now reference the schema and
  `pytest -k json_schema_validation` includes positive/negative coverage for the contract.
- Added `execution_model.schema.json` mirroring detailed design §3.6/§4.4 execution thresholds
  (human delay, slippage, entry-mode gating) and scaffolded `config/execution_model.yaml`. Smoke
  tests now validate the scaffold during `pytest -k config_schema_smoke`.

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
