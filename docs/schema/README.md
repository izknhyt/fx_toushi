# Shadow & Audit Schema Catalog

This folder collects human-readable references for the Shadow bridge and audit payloads consumed by
ops tooling. JSON Schema contracts live under `docs/schemas/`, while the documents here focus on API
and event shapes used by documentation readers.

## Contents

- `audit_event.md` – Field descriptions for `audit.*` events captured by `AuditWriter` (design §16).
- `broker_shadow.json` – Draft data contract for FillShadow artefacts produced by
  `FillShadowRecorder` and companions (§80.1).
- `shadow_gui.yaml` – OpenAPI 3.1 draft covering the Shadow GUI endpoints exposed by
  `ShadowGuiAPI` (§60.2).

Refer to `docs/schemas/README.md` for the authoritative JSON Schema registry and change-log
requirements when contracts evolve.
