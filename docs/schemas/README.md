# JSON Schema Registry

This directory hosts the canonical JSON Schema definitions that back Codex data contracts. Runtime
components load the same schema documents via the repository-level `schema/` symlinks, while the
materials stored here serve as the authoritative source for governance reviews and change logs
(detailed design §16.5–§16.6).

## Repository layout

- `accounts_profile.schema.json` – Account configuration contract used by
  `AccountAggregatorService` (§51.1). Validates `accounts/<broker>/<account_id>.yaml` files.
- `order_state.schema.json` – Order lifecycle and recovery plan contract consumed by
  `OrderStateStore` (§84.2) and broker CLI tooling.
- `strategy_manifest.schema.json` – Strategy activation manifest aligning with §3.5/§4.4.1 and
  Runbook STRAT-PROMOTE-01. Governs `config/strategy_manifest.yaml`.
- `feature_pipeline.schema.json` – Feature/indicator enablement contract for §3.4〜§3.5. Validates
  `config/feature_pipeline.yaml` prior to deterministic replay tests.
- `board_modes.schema.json` – Board mode guard configuration shared by §2.5/§3.5 and Runbook
  RUN-SPREAD-03. Validates `config/board_modes.yaml`.
- `execution_model.schema.json` – Execution model contract capturing §3.6 defaults, human delay
  distributions, entry-mode thresholds, and symbol/regime overrides (§4.4). Governs
  `config/execution_model.yaml` and validation templates under Runbook RUN-HITL-01 / RUN-RISK-01.
- `cfg.schema.json` – Mode profile configuration for SessionManager (§3.1/§4.4). Applies to
  `config/profiles/*.yaml`.
- `mode_context.schema.json` – Composite runtime context contract binding profile/clock/feed/execution/
  account/audit/session structures (§3.1.0/§4.2.5). Validates `snapshots/latest/mode_context.json`
  and ModeContextFactory outputs during startup validation.
- `human_gate_config.schema.json` – Human Gate / Reduce-Only advisor contract (§3.5.6/§5.12).
  Validates `config/reduce_only.yaml` and governs comment/role overrides in `config/profiles/*.yaml`.
- `sla_threshold_profile.schema.json` – Data ingestion SLA thresholds (§4.4/§9.4.4). Applies to
  `config/sla_thresholds/*.yaml`.
- `gate_state.schema.json` – Operational gate snapshot contract (§4.2/§5.4)。`market.news/calendar/spread`、`risk.reduce_only`、`human.double_entry_required` 等のネスト構造を定義し、`schema/gate_state.sample.json` および RUN-RISK-01 のスナップショット検証で参照される。
- `ops_config.schema.json` – Automation Effect Tracker thresholds/notification routing (§52.2).
  Governs `config/ops.yaml` for CLI automation workflows.
- `roles_config.schema.json` – CLI permission catalogue covering Ops/Research/Governance workflows
  (§52/§57/§68). Governs `config/roles.yaml` and Access Registry consistency checks.
- `risk_policy.schema.json` – Risk policy profiles, kill switch thresholds, and reporting guardrails
  (§5.2). Governs `config/risk_policy.yaml` for governance and audit workflows.
- `scoring_config.schema.json` – ScoringService coefficient, drift penalty, and diagnostics contract
  (§3.7/§4.4.4). Governs `config/scoring.yaml`.
- `scoreboard.schema.json` – Strategy Scoreboard thresholds, weightings, and watchlist rules
  (付録G.1/§4.4.5). Governs `config/scoreboard.yaml`.
- `guardrails_metrics.schema.json` – Guardrail telemetry (health/board_mode/kill_switch/spread_status/reasons/exit_code/reduce_only/ack_user/manifest_hash/data_hash/risk_disclosure/profit_readiness_status/auto_execute/auto_execute_forced_off) logged to `metrics/guardrails.jsonl` per detailed design §90.1.1 / status CLI.
- `data_ingestion_sla.jsonl`（スキーマ未固定だが運用契約） – `IngestionMetricsCollector` が resync/data fetch 過程で集計した `fetch_p95_ms`, `fetch_p99_ms`, `latency_status`, `retry_count`, `catch_up_lag_minutes` などを記録。raw観測は `metrics/raw/data_ingestion_raw_<date>.jsonl` に日次ローテーション（10万行で分割、60日後gzip/90日後削除の運用推奨）。清掃手順は `docs/runbooks/RUN-METRICS-CLEANUP.md` を参照。
- `spread_cooldown.schema.json` – Spread/NTP/News guard metrics for `metrics/spread_cooldown.jsonl` per §90.3 and `tradectl spread inspect`.
- `audit.health_action.schema.json` – Health action ack records (`logs/audit/health_action.jsonl`) for `tradectl status --ack` / Runbook RUN-DATA-05 evidence.
- `audit.kill_switch.schema.json` – Kill switch state transitions (`logs/audit/kill_switch.jsonl`) per §90.1.1 and `tradectl kill-switch set`.
- `audit.spread_guard.schema.json` – Spread guard audit entries (`logs/audit/spread_guard.jsonl`) produced by `tradectl spread inspect`.
- `performance_snapshot.schema.json` – KPI snapshot contract for backtest/paper/live modes (Sharpe,
  Sortino, max drawdown, win rate, P&L metadata) per detailed design §3.5.2/§7.6. A curated payload
  is stored at `docs/schemas/examples/performance_snapshot.sample.json`, and regression coverage
  lives in `tests/contracts/test_performance_snapshot_schema.py`.
- `risk_live_guard.schema.json` – Live Guard PF/Sharpe/latency guardrails and notification toggles
  (§3.8/§4.4.3). Governs `config/risk_live_guard.yaml`.
- `compliance_regression.schema.json` – Compliance regression metrics (`metrics/compliance_regression.json`)
  for Stop/Freeze & Capital Guard checks (§61.3).
- `degradation_playbook.schema.json` – Degradation playbook metrics (`metrics/degradation_playbook.jsonl`)
  for Acceptable Degradation orchestration (§66.3).
- `ops_readiness.schema.json` – Ops readiness score weights, evidence paths, and governance thresholds
  (§3.27/§4.4.6). Governs `config/ops_readiness.yaml`.
- `config_bundle.schema.json` – Aggregate schema ensuring the full config scaffolding is present and
  aligned with individual schemas. Used by `poetry run schema-validate config --schema ...`.
- `CHANGELOG.md` – Required update log whenever schema contracts evolve. Each PR touching the
  registry must append an entry summarising the change, linked to the relevant design/runbook
  context.
- Additional scaffolds (M1+ references): broker sandbox/error map/SLO, data sources and provider
  priority, ingestion priorities, event bus config, pipeline steps, compliance pretrade/risk
  disclosure, drift/emergency, idea/model risk registries, reconciliation/regression, KPI report
  config, resource budget, margin stress presets, shadow/share/signature configs, and SLA threshold
  candidates.

## Update workflow

1. Draft schema modifications under `docs/schemas/`, updating descriptions and enumerations to match
the design references.
2. Append a new section to `CHANGELOG.md` describing the change, the impacted systems, and any
   migration notes.
3. Mirror the update through the `schema/` directory using `python tools/sync_schema_registry.py`.
   Use `python tools/sync_schema_registry.py --check` in CI to detect drift.
4. Extend the validation suite in `tests/jsonschema/` so `pytest -k json_schema_validation` covers
   the new contract, and update `tests/config/test_config_schema_smoke.py` if a new config scaffold
   was added.
5. Adjust design docs, runbooks, and READMEs so path references stay consistent.

See §16.6 for the full Codex review checklist that applies to schema-level changes.
