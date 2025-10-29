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
- `cfg.schema.json` – Mode profile configuration for SessionManager (§3.1/§4.4). Applies to
  `config/profiles/*.yaml`.
- `sla_threshold_profile.schema.json` – Data ingestion SLA thresholds (§4.4/§9.4.4). Applies to
  `config/sla_thresholds/*.yaml`.
- `gate_state.schema.json` – Operational gate snapshot contract (§4.2/§5.4)。`market.news/calendar/spread`、`risk.reduce_only`、`human.double_entry_required` 等のネスト構造を定義し、`schema/gate_state.sample.json` および RUN-RISK-01 のスナップショット検証で参照される。
- `ops_config.schema.json` – Automation Effect Tracker thresholds/notification routing (§52.2).
  Governs `config/ops.yaml` for CLI automation workflows.
- `roles_config.schema.json` – CLI permission catalogue covering Ops/Research/Governance workflows
  (§52/§57/§68). Governs `config/roles.yaml` and Access Registry consistency checks.
- `CHANGELOG.md` – Required update log whenever schema contracts evolve. Each PR touching the
  registry must append an entry summarising the change, linked to the relevant design/runbook
  context.

## Update workflow

1. Draft schema modifications under `docs/schemas/`, updating descriptions and enumerations to match
the design references.
2. Append a new section to `CHANGELOG.md` describing the change, the impacted systems, and any
   migration notes.
3. Mirror the update through the `schema/` symlinks and extend the validation suite in
   `tests/schema/` so `pytest -k json_schema_validation` covers the new contract.
4. Adjust design docs, runbooks, and READMEs so path references stay consistent.

See §16.6 for the full Codex review checklist that applies to schema-level changes.
