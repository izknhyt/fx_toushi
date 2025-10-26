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
