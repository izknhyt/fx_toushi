# Design Alignment Roadmap

Scope: align all implementation and tests with `detailed_design_fx_signal_tool_v1.md`.

## Completion Definition
- Every row in `docs/design_alignment_backlog.md` is marked `done`.
- Each EP’s tests (as stated in the design doc) pass.
- Evidence artifacts and metrics paths defined in the design doc exist where applicable.

## Tracking Rules
- Each backlog row in `docs/design_alignment_backlog.md` gets:
  - `Status`: todo / in_progress / done
  - `Notes`: implementation refs and test commands
- The `Context` column disambiguates repeated EP IDs reused in different sections.
- Summary EP rows (e.g., `EP-01 DataLag Mitigation`) are umbrella entries and are marked `done` only after all related detailed EP rows are `done`.
- Each implementation batch updates:
  - backlog status + notes
  - relevant tests executed (record in Notes)

## Roadmap Phases (Top-Down)

### Phase 0 — Baseline & Traceability
Goal: freeze scope, identify all EP items, and set the tracking cadence.
- Backlog: `docs/design_alignment_backlog.md`
- Acceptance: backlog exists; status entries are populated for already-done items.

### Phase 1 — Core Runtime & Guardrails
Focus: EP01/EP02/EP03/EP04/EP05 items that define ingestion, determinism, guardrails, ticket UX, and reporting.
- EP01-P1..P3 (Data lag mitigation, manual CSV, resync evidence)
- EP02-P1..P3 (Determinism pipeline + replay)
- EP03-P1..P8 (Health/Spread/Kill Switch core loop + Liquidity/Dashboard items)
- EP04-P1..P3 (Ticket clarity + audit + GUI bridge)
- EP05-P1..P2 (Weekly review + benchmark)
Exit: core CLI flows and guardrails evidence are fully aligned.

### Phase 2 — Research / Stress / Journal / Benchmark
Focus: EP04/EP05/EP06 items for stress testing, trade journal, and research pipelines.
- Stress registry + engine (EP04-P1..P3)
- TradeJournal (EP04-P1..P3 in §34)
- Benchmark ingestion/replay (EP05-P1..P3)
- Research pipeline + drift (EP06-P1..P3, §26/§drift)
- Idea pipeline (EP06-IDEA-P1..P3)
- Research workspace/notebooks/artifacts (EP07-RSCH-P1..P3)
- Promotion gates (EP12-PROMO-P1..P3)
- Risk stress lab (EP12-STRESS-P1..P3)
- Experiment tracking (EP08-EXP-P1..P3)

### Phase 3 — Governance & Compliance
Focus: model risk, licensing, strategy board/lifecycle, access governance, risk consent.
- EP06-MR-P1..P4
- EP09-LIC-P1..P3
- EP09-RTF-P1..P3
- EP09-BRD-P1..P3
- EP09-LIFE-P1..P3
- EP10-COMP-P1..P3
- EP11-RISKCONSENT-P1..P3
- EP15-ACCESS-P1..P3

### Phase 4 — Ops / DocOps / Drills
Focus: Ops agenda, drills, documentation automation, readiness integrations.
- EP11-OPS-P1..P3
- EP11-DRILL-P1..P3
- EP12-DOC-P1..P5
- EP11-INC-P1..P3
- EP13-COACH-P1..P3
- EP14-DEGRADE-P1..P3

### Phase 5 — Finance / BackOffice / SecureShare
Focus: ledger/tax, evidence sharing, cost allocation.
- EP07-BO-P1..P3
- EP08-SS-P1..P3
- EP10-ACC-P1..P3
- EP05-P3..P5 (statement reconciliation)

### Phase 6 — Broker / Shadow / GUI
Focus: broker adapters, shadow flows, GUI layers.
- EP13-SHADOW-P1..P3
- EP17-BROKER-P1..P21
- EP18-GUI-P1..P3
- EP20-SHADOW-GW-P1..P3

### Phase 7 — Alpha / Experiments / Degradation / Regression
Focus: alpha loop, experimentation, degradation playbooks, regression suites.
- EP21-ALPHA-P1..P3
- EP16-REG-P1..P3

## Execution Cadence
- Implement by phase; each phase is split into batches of 3–6 EP items.
- After each batch:
  - update backlog status + notes
  - run tests listed by the design doc
  - record evidence output paths

## Start Here
1) Fill current status in `docs/design_alignment_backlog.md`.
2) Execute Phase 1 items in dependency order.
3) Continue through phases until backlog reaches `done` across all EP rows.
