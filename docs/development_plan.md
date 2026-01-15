# Development Plan & Task Tracker

Single source of truth for development policy, milestone status, and task tracking.

## How to use
- Update status and checklist items here first.
- Add notes to the backlog rows when you complete implementation or run tests.
- Keep evidence paths and test commands in Notes where applicable.
- Codex rule: after any implementation/change, update this file in the same PR/patch.

## Update Protocol (Codex)
When a task is implemented or reviewed:
- Update the Unified Task Table status and evidence/notes.
- Update the Design Alignment Backlog row (status + notes).
- Tick the Implementation Review Checklist items that were completed.
- Add/refresh evidence paths and test commands.
- Cross-check the completed work against the relevant sections of `detailed_design_fx_signal_tool_v1.md` and note any deviations or confirmations in the Notes.
- Append a new entry to the Update Log with UTC time to the minute.
- Use `make update-log MSG="..."` (or `python3 tools/update_log.py "..."`) to avoid timestamp mistakes.
- If a Runbook is edited, bump its version and update last updated metadata.
- If Codex asks a clarifying question, log it in the Codex Q&A Log with default SLA (6h) and respond in Q/A format with design refs.
 - If a design ambiguity is found, log it in the Codex Q&A Log, mark Status as open, and pause the change until a response is recorded (unless explicitly instructed to proceed).

## Update Log (UTC)
- 2026-01-12T03:36Z — Added Update Log and timestamp rule.
- 2026-01-12T03:39Z — Added archive README, doc editing policy, and AGENTS finish checklist rule.
- 2026-01-12T03:55Z — Doc cleanup: update log tool + doc reference alignment + archive moves
- 2026-01-12T03:57Z — Aligned runbooks/templates to development_plan and archived historical agendas/risk reviews
- 2026-01-12T03:58Z — Updated legacy risk_review references and cleaned remaining doc links
- 2026-01-12T04:18Z — Runbook metadata refreshed and added check-doc-refs guard
- 2026-01-12T04:29Z — Bumped runbook versions and simplified PR checklist
- 2026-01-12T04:31Z — Added runbook version bump rule to update protocol
- 2026-01-12T05:44Z — M1 FR-01/02 review: normalize timestamp parsing, fix manual CSV path, add mixed tz test
- 2026-01-12T05:57Z — M1 FR-03 review: normalize compute timestamps to UTC, refresh cache-hit context, add mixed TZ + cache context tests
- 2026-01-12T06:45Z — Ran feature pipeline integration tests (pytest tests/integration/test_feature_pipeline.py)
- 2026-01-12T06:48Z — FR-03 review: add ISO8601 fallback for mixed timestamp strings in feature pipeline
- 2026-01-12T06:51Z — FR-04 review: validate explicit watchlists and guard Donchian mid-band missing values
- 2026-01-12T08:00Z — FR-04 review: ran strategy engine + determinism integration tests
- 2026-01-12T08:04Z — FR-05 review: preserve hard-stop precedence over soft-stop triggers in RiskManager
- 2026-01-12T08:12Z — FR-06 review: floor lot rounding and enforce min lot after rounding
- 2026-01-12T08:29Z — FR-07 review: mark spread watch as warn in ticket checklist
- 2026-01-12T09:08Z — FR-08 review: guard session start against existing log and ensure manager stop on failure
- 2026-01-12T09:10Z — FR-10 review: resolve metric state from CSV KPI sources
- 2026-01-12T09:13Z — FR-16/18 review: snapshot metadata uses UTC-aware timestamps
- 2026-01-12T09:15Z — Ran M1 regression test batch (data/feature/strategy/risk/ticket/session/report/resync/snapshot/mode context)
- 2026-01-12T09:19Z — FR-28 review: fix funding sync evidence runbook reference
- 2026-01-12T09:27Z — Captured resync ops evidence (reports/ops/resync/20260112T092627.665111Z.md) via tradectl resync
- 2026-01-12T09:47Z — M1.1 provider integrations: add provider profiles + paid feed adapter, update config schema bundle and tests
- 2026-01-12T09:48Z — M1.1 provider integrations: allow explicit provider_profiles override; reran data service + config schema tests
- 2026-01-12T10:08Z — M1.1 weekly report extended blocks: add risk summary builder and tests
- 2026-01-12T10:30Z — EP11-DRILL-P1: harden OpsDrillService with runbook validation, drill report rendering, metrics/events, and tests
- 2026-01-12T10:43Z — EP11-DRILL-P2: add drill CLI commands/wiring and tests
- 2026-01-12T10:56Z — EP11-DRILL-P3: integrate OpsAgenda drill pending, OpsEvidenceStore, and automation effect hooks
- 2026-01-12T11:16Z — EP11-OPS-P1: add ops worklog CLI add/list, tests, and query timezone normalization
- 2026-01-12T11:21Z — EP11-OPS-P2: add automation effect CLI/report tool and metrics/audit hooks
- 2026-01-12T11:24Z — EP11-OPS-P3: add ops agenda CLI rendering plus metrics/audit logging
- 2026-01-12T11:28Z — EP11-INC-P1: add incident postmortem service, template, and unit tests
- 2026-01-12T11:30Z — EP11-INC-P2: add trade forensics analyzer and ops incident CLI flow
- 2026-01-12T11:32Z — EP11-INC-P3: add incident metrics, validation playbook stub, and runbook
- 2026-01-12T11:38Z — EP11-RISKCONSENT-P1..P3: add risk consent enforcer, device bindings, CLI, and validation/runbook updates
- 2026-01-12T11:49Z — M1.1 review fixes: enforce device binding encryption + risk consent metrics fields + postmortem timing metrics
- 2026-01-12T11:55Z — Add Codex Q&A log section with design-aligned SLA protocol
- 2026-01-12T12:07Z — M1.1 review fixes: add cryptography dep, enforce device binding errors, ops agenda critical/runbook/validation logic, postmortem timeline min/max; tests: pytest tests/unit/test_ops_agenda_status.py tests/unit/test_ops_agenda_drills.py tests/unit/test_risk_disclosure_enforcer.py tests/unit/test_device_binding_service.py tests/unit/test_incident_postmortem_service.py
- 2026-01-12T12:07Z — Log Codex Q&A entry for clarification on question handling scope
- 2026-01-12T12:19Z — M1.1 review fixes: risk consent CLI error exit, ops agenda degraded_ack completion, postmortem non-negative timing clamp; tests: pytest tests/unit/test_ops_agenda_status.py tests/unit/test_compliance_risk_cli.py tests/unit/test_risk_disclosure_enforcer.py tests/unit/test_incident_postmortem_service.py
- 2026-01-12T12:28Z — M1 review fixes: preserve ticket determinism hash, resync unavailable status, funding numeric normalization; tests: pytest tests/unit/test_cli_ticket_actions.py tests/unit/test_cli_resync.py tests/cli/test_funding_cli.py
- 2026-01-12T13:03Z — M1 review fixes: enforce reduce-only under guarded health + surface kill switch runbook; tests: pytest tests/unit/test_health_state.py
- 2026-01-12T13:25Z — M1 review fixes: ticket risk_disclosure normalization, gate-state double-entry enforcement, guardrails health_state default; tests: pytest tests/unit/test_cli_ticket_actions.py tests/unit/test_ticket_builder.py tests/unit/test_ticket_builder_gate_state.py
- 2026-01-12T13:45Z — M1 resync health review: use degraded for 30m catch-up lag; add unit test for CLI health state
- 2026-01-12T13:58Z — M1 determinism review: replay diff_count now computed per strategy; added determinism replay unit test
- 2026-01-12T14:15Z — M2 status整理: stress/journal/benchmarkの既存実装をバックログへ反映し、M2+をin_progressに更新
- 2026-01-12T14:35Z — M3整理: M3+ガバナンス/コンプラの現状を追記し、EP15-ACCESS-P1をin_progressに更新
- 2026-01-12T14:38Z — Design/backlog EP突合: EP表記ゆれ（EP-XX/EPXX）を正規化して網羅確認を記録
- 2026-01-12T21:57Z — EP02 evidence: generated metrics/replay_jobs.jsonl and metrics/feature_cache.jsonl; marked EP-02/EP02-P3/EP02-T1 done
- 2026-01-12T21:59Z — Update protocol: add design cross-check requirement and ambiguity handling via Q&A log
- 2026-01-12T22:04Z — EP01-P3整理: resync証跡/metrics確認済みとしてEP-01/EP01-P3をdoneへ更新
- 2026-01-12T22:25Z — EP03-P6..P8: add liquidity monitor/service/CLI, gate-state integration, ops dashboard, emergency stub, runbooks; tests for liquidity + dashboard

## Codex Q&A Log
When Codex asks a clarifying question, track it here instead of `docs/prompt_packages/` (legacy).
Default SLA: 6 hours unless otherwise specified.

| Logged (UTC) | Question | SLA | Response Summary | Design References | Status |
| --- | --- | --- | --- | --- | --- |
| 2026-01-12T12:05Z | 「質問関係」の対象機能を確認。 | 6h | 推奨設定で進行し、設計準拠で質問対応プロトコルを`docs/development_plan.md`に集約。 | `detailed_design_fx_signal_tool_v1.md` §12.3.5 | closed |

## Current Status Snapshot (2026-01-12)
- M1 quality checklist: complete.
- M1 core gaps: weekly report risk summary/extended blocks implemented; remaining work is M1.1+ governance/drills/docs.
- M2+ scaffolds detected: stress registry/engine, TradeJournal CLI/service, benchmark compare exist but are partial.
- M3+ partials: risk consent completed; access review start scaffolded; licensing/board/lifecycle/compliance governance mostly todo.
- Design EP coverage check: EP IDs (EP-XX vs EPXX) normalized; backlog coverage matches design EP list.
- Design Alignment Backlog totals: 162 entries (done 41 / in_progress 4 / todo 117).
- Deprecated duplicates removed; historical copies can be found in git history if needed.
- Archived legacy docs under `docs/archive/` (change_requests, prompt_packages, implementation_packets, daily_agenda, releases, risk_review, review_log, missing_assets_inventory).

## Unified Task Table (High-Level)
This is the single table for tracking what is done vs. not done. Use it as the primary view.

| Task | Scope | Status | Evidence / Notes | Next Action |
| --- | --- | --- | --- | --- |
| M1 Core: Data ingestion & quality | M1 | Done | `src/data/service.py`, `src/interfaces/cli/data.py`; review fixes in `src/data/quality.py`, `src/data/manual_csv.py`; tests: `pytest tests/unit/test_data_quality_guard.py` | None. |
| M1 Core: Feature pipeline | M1 | Done | `src/features/pipeline.py`, `src/features/bar_ready.py`; review fixes for ISO8601 UTC normalization + cache-hit context refresh; tests: `pytest tests/unit/test_feature_pipeline_compute.py`, `pytest tests/integration/test_feature_pipeline.py` | None. |
| M1 Core: Signal engine | M1 | Done | `src/strategies/registry.py`, `src/strategies/donchian.py`; review fixes for watchlist validation + missing Donchian mid guard + determinism replay diff_count per strategy; tests: `pytest tests/unit/test_strategy_registry_contracts.py tests/unit/test_donchian_strategy.py tests/unit/test_diagnostics_determinism.py`, `pytest tests/integration/test_strategy_engine.py tests/integration/test_strategy_determinism.py` | None. |
| M1 Core: Risk manager | M1 | Done | `src/risk/manager.py`, `src/core/health.py`, `src/risk/liquidity_monitor.py`, `src/ops/dashboard.py`; review fixes ensure hard-stop not downgraded by soft-stop triggers + guardrail reduce-only enforcement + kill switch runbook surfaced + liquidity monitor/ops dashboard guardrails; tests: `pytest tests/unit/test_risk_manager.py tests/unit/test_health_state.py tests/unit/test_liquidity_monitor.py tests/unit/test_ops_dashboard.py` | None. |
| M1 Core: Position sizing | M1 | Done | `src/sizing/position_sizer.py`, `src/sizing/rounding.py`; review fixes for floor rounding to avoid oversizing; tests: `pytest tests/unit/test_rounding.py tests/unit/test_ticket_builder.py` | None. |
| M1 Core: Ticket/HITL | M1 | Done | `src/ticket/builder.py`, `src/ticket/validators.py`, `src/interfaces/cli/tickets.py`; review fixes: spread watch marks checklist warn + determinism hash preserved + gate-state double-entry enforcement + risk_disclosure status normalization; tests: `pytest tests/unit/test_ticket_builder.py tests/unit/test_ticket_builder_gate_state.py tests/unit/test_cli_ticket_actions.py` | None. |
| M1 Core: Mode switching | M1 | Done | `src/core/session.py`, `src/interfaces/cli/session.py`; review fix ensures log path checked before start and manager stop on failure; tests: `pytest tests/cli/test_session_cli.py` | None. |
| M1 Core: Weekly report | M1 | Done | `src/interfaces/cli/report.py`, template; review fix: metric state supports CSV KPI sources; tests: `pytest tests/unit/test_cli_report.py` | Extended blocks are enabled in M1.1. |
| M1 Core: Resync & snapshot | M1 | Done | `src/core/resync.py`, `src/interfaces/cli/resync.py`, `src/core/snapshot.py`; review fixes: snapshot timestamps are UTC-aware + resync returns unavailable when session missing + catch-up lag 30m maps to degraded; tests: `pytest tests/unit/test_event_bus_snapshot_placeholder.py tests/unit/core/test_event_bus_snapshot_scaffold.py tests/unit/test_cli_resync.py`; ops evidence: `reports/ops/resync/20260112T092627.665111Z.md` | None. |
| M1 Core: Funding service | M1 | Done | `src/funding/service.py`, `src/interfaces/cli/funding.py`; review fixes: runbook reference corrected + numeric formatting normalization; tests: `pytest tests/cli/test_funding_cli.py` | None. |
| M1.1+ Provider integrations | M1.1+ | Done | Provider profiles (`config/provider_profiles/local.yaml`), paid feed adapter (`src/data/providers/paid_feed.py`), config scaffold (`config/data_sources/paid_feed.yaml`), service wiring (`src/data/service.py`); tests: `pytest tests/unit/test_data_service_sla.py tests/unit/test_data_service_backfill.py tests/config/test_config_schema_smoke.py` | None. |
| M1.1+ Weekly report extended blocks | M1.1+ | Done | `RiskSummary` summary from risk policy/logs, extended blocks wired in `src/interfaces/cli/report.py`; tests: `pytest tests/unit/test_cli_report.py` | None. |
| M1.1+ Governance/Drills/Docs hardening | M1.1+ | Done | OpsDrillService hardening + CLI drill commands + OpsAgenda/Evidence/Automation integration + runbook/validation/critical-first agenda logic (degraded_ack completion) (`src/ops/drills.py`, `src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`, `src/ops/evidence.py`, `src/ops/agenda.py`); tests: `pytest tests/unit/test_ops_drill_service.py tests/unit/test_cli_ops_drills.py tests/unit/test_ops_evidence_store.py tests/unit/test_ops_agenda_drills.py tests/unit/test_ops_agenda_status.py` | None. |
| M1.1+ Ops automation track | M1.1+ | Done | OpsWorklog + AutomationEffect + OpsAgenda CLI/metrics/audit (`src/ops/worklog.py`, `src/ops/automation.py`, `src/ops/agenda.py`, `src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`, `tools/automation_effect_report.py`); tests: `pytest tests/unit/test_ops_worklog_service.py tests/integration/test_ops_cli.py tests/unit/test_automation_effect_tracker.py tests/integration/test_ops_automation_cli.py tests/integration/test_ops_agenda_cli.py` | None. |
| M1.1+ Incident postmortem tooling | M1.1+ | Done | Postmortem metrics now include detect/contain timing + evidence hash in validation (`src/ops/postmortem.py`, `docs/validation_playbook/AC43_postmortem.yaml`, `docs/runbooks/RUN-INC-01.md`); timing uses min/max timeline bounds + clamps non-negative; tests: `pytest tests/unit/test_incident_postmortem_service.py tests/unit/test_trade_forensics_analyzer.py tests/integration/test_ops_incident_cli.py` | None. |
| M1.1+ Risk consent enforcement | M1.1+ | Done | Enforcer metrics/audit fields align with design; device registry encrypted-at-rest with 600 perms + `cryptography` dependency; CLI warns + exits on device binding failure (`src/compliance/risk_disclosure_enforcer.py`, `src/compliance/device_binding.py`, `src/interfaces/cli/compliance_risk.py`, `src/interfaces/cli/__init__.py`, `docs/validation_playbook/AC44_risk_consent.yaml`, `docs/runbooks/COMPLIANCE-01.md`, `pyproject.toml`); tests: `pytest tests/unit/test_risk_disclosure_enforcer.py tests/unit/test_device_binding_service.py tests/integration/test_risk_consent_flow.py tests/unit/test_compliance_risk_cli.py` | None. |
| M2+ Research/Stress/Ideas/Governance | M2+ | In progress | Stress registry/engine + TradeJournal CLI/service + Benchmark compare are scaffolded (`src/stress/*`, `src/journal/service.py`, `src/interfaces/cli/benchmark.py`, `src/reporter/benchmark.py`); ingestion/validation/research pipelines remain | Pick a phase batch and plan. |
| M3+ Governance & Compliance | M3+ | In progress | Risk consent is implemented (`src/compliance/*`, `src/interfaces/cli/compliance_risk.py`); access review start is scaffolded (`src/interfaces/cli/access_review.py`, `src/interfaces/cli/__init__.py`); licensing/board/lifecycle/compliance/access governance tracks remain | Pick a phase batch and plan. |

## Release Checklist
When preparing a release, follow `docs/release_checklist.md`. This is separate from the day-to-day task tracking above.

## Implementation Review Checklist
Use this checklist after completing a task or batch.

- [x] Evidence artifacts captured (logs/reports paths noted).
- [x] Tests executed and recorded in Notes.
- [ ] CLI output verified for user-facing flows.
- [x] Docs updated in this file (status + evidence).
- [x] Optional refactor/cleanup complete (if needed).

## Development Policy
Scope: align all implementation and tests with `detailed_design_fx_signal_tool_v1.md`.

## Completion Definition
- Every row in the Design Alignment Backlog section is marked `done`.
- Each EP’s tests (as stated in the design doc) pass.
- Evidence artifacts and metrics paths defined in the design doc exist where applicable.

## Tracking Rules
- Each backlog row in the Design Alignment Backlog section gets:
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
- Backlog: Design Alignment Backlog section in this doc.
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
1) Fill current status in the Design Alignment Backlog section.
2) Execute Phase 1 items in dependency order.
3) Continue through phases until backlog reaches `done` across all EP rows.

## M1 Implementation Status
- Source: `detailed_design_fx_signal_tool_v1.md` §0.7 M1 Core traceability table.
- Status definitions:
  - Implemented: core behavior and CLI/tests exist for M1 scope.
  - Partial: scaffolding or incomplete behavior; interfaces/tests exist.
  - Stub: placeholder with minimal logic only.
  - Not started: no matching implementation found.
- Status is based on the completion criteria listed below.
- Scope: repository code + tests only (runtime verification not performed).

## M1 Core Feature Map

| Feature (FR) | Status | Evidence (code/tests) | Notes / Gaps |
| --- | --- | --- | --- |
| FR-01/FR-02 Data ingestion & quality | Implemented | `src/data/service.py`, `src/data/quality.py`, `src/data/manual_csv.py`, `src/interfaces/cli/data.py`, `tests/unit/test_data_service_sla.py`, `tests/unit/test_manual_csv_reconciler.py` | Provider profiles + paid feed adapter available behind `data.paid_feed`. |
| FR-03 Feature pipeline | Implemented | `src/features/pipeline.py`, `src/features/bar_ready.py`, `tests/unit/test_feature_pipeline_compute.py`, `tests/integration/test_feature_pipeline.py`, `tests/integration/test_strategy_engine.py` | compute_feature_matrix ISO8601-aware UTC normalization and cache-hit context refresh. |
| FR-04 Signal engine | Implemented | `src/strategies/registry.py`, `src/strategies/ma_rsi.py`, `src/strategies/donchian.py`, `tests/unit/test_strategy_plugin_contract.py`, `tests/integration/test_strategy_engine.py` | Validates provided watchlists against feature context; Donchian mid-band missing guard; integration determinism tests pass. |
| FR-05 Risk manager | Implemented | `src/risk/manager.py`, `src/core/gate.py`, `tests/unit/test_risk_manager.py`, `tests/unit/test_gate_aggregator.py` | Hard-stop precedence enforced over soft-stop triggers. |
| FR-06 Position sizing | Implemented | `src/sizing/position_sizer.py`, `src/ticket/builder.py`, `src/sizing/fractional.py`, `src/sizing/rounding.py` | Lot rounding floors to step to avoid oversizing; min lot enforced. |
| FR-07 Ticket/HITL | Implemented | `src/ticket/builder.py`, `src/interfaces/cli/tickets.py`, `src/ticket/checklist.py`, `tests/unit/test_ticket_builder.py`, `tests/unit/test_cli_ticket_actions.py` | Spread watch treated as warn in checklist; guard-mode reduce-only enforcement and approval warnings wired. |
| FR-08 Mode switching | Implemented | `src/core/session.py`, `src/interfaces/cli/session.py`, `tests/cli/test_session_cli.py` | Start/stop flow guards log collisions and stops manager on error; HITL profile normalization present. |
| FR-10 Weekly report | Implemented | `src/reporter/generator.py`, `src/interfaces/cli/report.py`, `src/reporter/templates/weekly_m1_core.md`, `tests/cli/test_tradectl_report_weekly.py` | metric_state handles CSV/Parquet KPI sources for paper profile. |
| FR-16/FR-18 Resync & snapshot | Implemented | `src/core/resync.py`, `src/interfaces/cli/resync.py`, `src/core/snapshot.py`, `tests/unit/test_resync_coordinator.py` | Snapshot metadata timestamps are UTC-aware; session catch-up updates snapshots and health thresholds. |
| FR-28 Funding service | Implemented | `src/funding/service.py`, `src/funding/loaders.py`, `src/interfaces/cli/funding.py`, `tests/cli/test_funding_cli.py` | Funding evidence runbook reference corrected. |

## M1 Completion Criteria Checks (Design-Derived)

### FR-01/FR-02 Data ingestion & quality

Criteria (from §0.7):
- [x] Inputs include yfinance 5m, Dukascopy HTTP burst, manual-fallback twin CSV, and `config/sla_thresholds/*.yaml`.
- [x] Normalized bars supplied to a `bar_ready_queue`/downstream buffer.
- [x] Emit `metrics/data_ingestion_sla.jsonl` with latency/429 metrics.
- [x] Emit `metrics/rate_limit_window.jsonl` with `stage_eval` entries.
- [x] Manual CSV hash audit recorded for twin CSV validation.
- [x] `health.changed` recommendations + Acceptable Degradation board-mode guidance wired to Runbook `RUN-DATA-05/06`.
- [x] Manual stage promotion/rollback requires `degraded_ack.registered` event.
- [x] Catch-up/parallelism targets (4 workers, 6 in catch-up, 30 min catch-up) enforced with Runbook gating.

Assessment: Implemented.

### FR-03 Feature pipeline

Criteria (from §0.7):
- [x] Indicator set for SMA/EMA/RSI/BB/ATR/MACD/Donchian/Zscore with per-indicator enable flags in `config/feature_pipeline.yaml`.
- [x] `FeatureFrame`/`FeatureContext` updated per symbol/timeframe with indicator cache.
- [x] `metrics/pipeline.jsonl` emitted with CPU/latency and indicator count.
- [x] ThreadPoolExecutor offload + 1h/1d resampling.
- [x] 5m bar arrival triggers delta recompute (explicit schedule).
- [x] Feature flags for M2 features exist and default false (no extra indicators enabled).
- [x] Enforce "SMA/EMA/RSI/ATR always enabled" rule beyond config defaults.
- [x] Dedicated integration test `tests/integration/test_feature_pipeline.py` (design note).

Assessment: Implemented.

### FR-04 Signal engine

Criteria (from §0.7):
- [x] Strategy registry + manifest validation with priorities/weights from `config/strategy_manifest.yaml`.
- [x] Determinism hash emitted per strategy run.
- [x] `signal.generated` events emitted.
- [x] Guarded mode suppresses new proposals and governance feature flags are honored.
- [x] Badges/score outputs reflected for downstream ticketing.

Assessment: Implemented.

### FR-05 Risk manager

Criteria (from §0.7):
- [x] Kill switch + reduce-only evaluation logic with drawdown/R_eff thresholds.
- [x] GateState integration for risk metadata and board_mode suggestion.
- [x] Thresholds sourced from `risk_policy.yaml` (0.75%/2.5%/5%) and FundingCurve input.
- [x] Spread/correlation metrics wired into risk decisions.
- [x] `risk.decision` event emission and `health.changed` notifications.
- [x] Acceptable Degradation reduce-only enforcement + Runbook gating.

Assessment: Implemented.

### FR-06 Position sizing

Criteria (from §0.7):
- [x] Fixed fractional sizing + rounding helpers exist.
- [x] PositionSizer emits size + OCO recommendations and respects broker lot/distance rules.
- [x] PositionSizer is wired into the ticket flow (draft metadata inputs for equity/risk/stop distance/ATR).

Assessment: Implemented.

### FR-07 Ticket/HITL

Criteria (from §0.7):
- [x] Ticket JSONL output + audit logging from CLI actions.
- [x] `HumanErrorChecklist` order/labels match design (`spread_window_clear` → `manual_comment_logged`).
- [x] News/Calendar/Spread gates enforced during ticket build.
- [x] Risk disclosure status surfaced in `tradectl board` header/banners.
- [x] BoardMode=guarded enforces Reduce-Only only.
- [x] TTL monitoring and missing-input warnings (OCO ack, manual comment) wired to approvals.

Assessment: Implemented.

### FR-08 Mode switching

Criteria (from §0.7):
- [x] ModeProfile loading + ModeContext factory (`tradectl start --profile`).
- [x] Mode-specific data source/execution settings resolved from `config/profiles/*.yaml`.
- [x] HITL flow behavior is consistent across modes.
- [x] Post-resync consistency check (design calls for validation after catch-up).

Assessment: Implemented.

### FR-10 Weekly report

Criteria (from §0.7):
- [x] Weekly Markdown generated from `weekly_m1_core.md` template.
- [x] KPI single values (Sharpe/MaxDD/WinRate/CumR) extracted in CLI.
- [x] `RiskSummaryStub` is used when the M1.1 flag is disabled.
- [x] `metrics/data_ingestion_sla.jsonl` is summarized when extended blocks are enabled.
- [x] Paper 90-day warm-up sets metric_state=provisional.
- [x] Update `reports/performance/<mode>/` when `reports.performance.enable` is enabled (M1.2).

Assessment: Implemented.

### FR-16/FR-18 Resync & snapshot

Criteria (from §0.7):
- [x] Resync job queue + `catch_up_lag_minutes` metrics + `resync.completed` event emission.
- [x] Manual CSV required flag propagated in resync queue processing.
- [x] Snapshot update integrated with session/catch-up lifecycle (beyond persistence).
- [x] 20 min warning / 30 min degraded thresholds + Runbook-driven recovery enforced.
- [x] Restart-time snapshot consistency check enforced.

Assessment: Implemented.

### FR-28 Funding service

Criteria (from §0.7):
- [x] Funding CSV loader + `tradectl funding sync/status` state handling.
- [x] FundingCurve integrates Calendar triple-day adjustments and produces `swap_penalty`.
- [x] Swap/Funding values propagated into Account/Reporter outputs.
- [x] Funding evidence output to `reports/validation_log/AC-09_funding_<date>.md`.

Assessment: Implemented.

## M1 Core Gaps (High Signal)

- None identified; remaining work tracked in M1.1+ tasks.

## Notes for Next Pass

- If we keep this doc, we should link evidence reports (e.g., `reports/validation_log/*`) per FR once we agree on the acceptance criteria for M1-only scope.

## M1 Quality Checklist
Use this list to decide whether M1 is "done" enough for the next phase.

## Automated Checks

- [x] `pytest tests/integration/test_strategy_engine.py`
- [x] `pytest tests/integration/test_feature_pipeline.py`
- [x] `pytest tests/unit/test_risk_manager.py`
- [x] `pytest tests/unit/test_cli_report.py`
- [x] `pytest tests/unit/test_funding_curve.py`
- [x] `pytest tests/cli/test_funding_cli.py`

## Manual Verification

 - [x] `tradectl pipeline drain-bar-ready` updates feature pipeline with recent `bar.ready` events.
 - [x] `tradectl data status --log-stage-eval` writes `metrics/rate_limit_window.jsonl` with
      `degraded_ack` gate and catch-up parallelism flags.
- [x] `tradectl report weekly --profile paper --dry-run` shows `metric_state=provisional`
      when fewer than 90 days of returns/equity are available.
      (Verified with `reports.performance.enable=true` for paper.)
- [x] `tradectl funding sync` writes `reports/validation_log/AC-09_funding_<date>.md`.
- [x] `tradectl status --json` includes `funding_state` and updated snapshot section.

## Evidence Artifacts

- [x] `logs/events/signal.generated.jsonl` contains recent `signal.generated` events.
- [x] `logs/events/risk.decision.jsonl` contains recent `risk.decision` events.
- [x] `logs/events/health.changed.jsonl` includes runbook references.

## M1–M1.2 Gap List
This table tracks gaps between the detailed design and current implementation
for the M1–M1.2 milestones. Use it to pick the next batch of work.

Legend:
- Status: missing / partial / done
- Priority: P0 (blocker), P1 (next), P2 (later)

| ID | Milestone | Design Ref | Requirement | Current State | Gap | Priority | Suggested Next Step |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G-01 | M1 Core | §89.1, §2.3, §3.15 | Resync orchestration: enqueue, pause signal flow, trigger backfill pipeline, emit ResyncCompleted chain | Resync queue + `ResyncCoordinator` drains jobs; `SessionManager.catch_up` toggles `catch_up_state` | None (M1 scope) | P0 | Done |
| G-02 | M1 Core | §3.1, §89.1, §1636 | `DataIngestionService.backfill` real fetch + 6h chunking + retry + manual CSV fallback | Backfill uses provider handlers, chunking, retries, SLA logs | None (M1 scope) | P0 | Done |
| G-03 | M1 Core | §3.15 | Resync latency metrics + resync lag health raise | Resync latency metrics logged; resync lag health raise at 30m (degraded); SnapshotManager data mismatch event logged; test: `pytest tests/unit/test_cli_resync.py` | None (M1 scope) | P1 | Done |
| G-04 | M1 Core | §3.1 (1588), §89 | Fetch/processing delay separation in pipeline | BufferCoordinator queue timestamps applied to fetch/processing delays | None (M1 scope) | P1 | Done |
| G-05 | M1 Core | §90.3 | NTP drift + news calendar integration into Spread Guard | Spread monitor enriches NTP drift + calendar event hints; CLI writes cooldown_eta | None (M1 scope) | P1 | Done |
| G-06 | M1.1 | §2567, RUN-FEATURE-FLAG-01 §5.2 | Reduce-Only Advisor real evaluation + audit fields | Reduce-Only advisor checks spread/latency/slippage/kill switch | None (M1 scope) | P1 | Done |
| G-07 | M1.1 | §2897, §2925 | Risk disclosure enforcement (block high-risk ops) + consent telemetry | Enforcement path present; metrics log added | None (M1 scope) | P1 | Done |
| G-08 | M1.1 | §2640 | Reporter extended blocks populate actual summaries | Extended blocks load risk summary + kill switch/spread/data quality/resync/manual CSV summaries (`src/interfaces/cli/report.py`, `tests/unit/test_cli_report.py`) | None (M1 scope) | P1 | Done |
| G-09 | M1.1 | §3491 | `tradectl config validate` CLI | CLI wrapper added, writes `reports/validation_log/config_<date>.md` | None (M1 scope) | P2 | Done |
| G-10 | M1.2 | §1.10, RUN-FEATURE-FLAG-01 §5.5 | Performance Snapshot flag gating + auto report integration | Feature flag gate added; weekly report auto-includes snapshot when enabled | None (M1 scope) | P1 | Done |
| G-11 | M1.2 | §49–§50 | Paid feed evaluation + licensing governance integration | Capability registry + evaluator + data status integration added | None (M1 scope) | P1 | Done |

Notes:
- Additional M1.1 Hardening items (audit bundle, release gate, ops drill orchestrator) are not listed here yet; add if you want to pursue the full hardening scope.

## Design Alignment Backlog
Source: detailed_design_fx_signal_tool_v1.md

| EP ID | Context | Design Ref | Status | Notes |
| --- | --- | --- | --- | --- |
| `EP-01 DataLag Mitigation` | 0.6.3 実装優先度マトリクス（M1） | detailed_design_fx_signal_tool_v1.md:170 | done | SLAログ/手動CSV/Resyncは実装済（`src/data/service.py`, `src/interfaces/cli/data.py`, `src/interfaces/cli/resync.py`）。`FallbackRetryTask`/`ManualCsvReconciler`は実装済（`src/data/fallback.py`, `src/data/manual_csv.py`）。Provider profiles/paid feed adapterを追加（`config/provider_profiles/local.yaml`, `src/data/providers/paid_feed.py`, `config/data_sources/paid_feed.yaml`）。`tools/sla_report.py`/`make sla-report`を実装済。Resync証跡: `logs/resync/resync_events.jsonl`, `reports/validation_log/AC-04_20251117.md`, `reports/validation_log/resync_failover_20260108.json`, `reports/ops/resync/20260112T092627.665111Z.md`, `metrics/data_ingestion_sla.jsonl`。CLIは`session`未注入でスタブ経路。 |
| `EP-02 Strategy Determinism` | 0.6.3 実装優先度マトリクス（M1） | detailed_design_fx_signal_tool_v1.md:171 | done | Feature determinism/registry/replayは実装済（`src/features/pipeline.py`, `src/strategies/registry.py`, `src/interfaces/cli/determinism.py`）。`board_diagnostics` CLIは実装済（`src/interfaces/cli/board_diagnostics.py`）。`metrics/determinism.jsonl`/`metrics/replay_jobs.jsonl`/`metrics/feature_cache.jsonl`の証跡を確認。Determinism replay diff_countは戦略単位で集計（`src/interfaces/cli/determinism.py`、`pytest tests/unit/test_diagnostics_determinism.py`）。Feature pipeline computeはISO8601 UTC正規化とcache-hit context更新を追加済（`pytest tests/unit/test_feature_pipeline_compute.py`, `pytest tests/integration/test_feature_pipeline.py`）。Signal engineはwatchlist検証とDonchian mid欠落ガードを追加（`pytest tests/unit/test_strategy_registry_contracts.py tests/unit/test_donchian_strategy.py`, `pytest tests/integration/test_strategy_engine.py tests/integration/test_strategy_determinism.py`）。 |
| `EP-03 Guardrails` | 0.6.3 実装優先度マトリクス（M1） | detailed_design_fx_signal_tool_v1.md:172 | done | Health/Spread/Kill SwitchとGuardrails整合は実装済（`src/core/health.py`, `src/interfaces/cli/status.py`, `src/interfaces/cli/spread.py`, `schema/guardrails_metrics.schema.json`）。Kill switchはhard-stop優先を保持（`src/risk/manager.py`、`pytest tests/unit/test_risk_manager.py`）。Position sizingはfloor丸めで過大発注を抑制（`src/sizing/rounding.py`, `pytest tests/unit/test_rounding.py`）。LiquidityMonitor/CLI/Board統合 + Ops Dashboard + Emergency stubを追加（`src/risk/liquidity_monitor.py`, `src/interfaces/cli/liquidity.py`, `src/interfaces/cli/ops_dashboard.py`, `src/ops/dashboard.py`, `src/ops/emergency.py`）。証跡: `reports/validation_log/AC-03_guardrails_20260110.md`（`profit_readiness_smoke`/`guardrails_latency_fallback`は収集0件）。 |
| `EP-04 Ticket Clarity` | 0.6.3 実装優先度マトリクス（M1） | detailed_design_fx_signal_tool_v1.md:173 | done | TicketRecord v2/Board/Ticket CLI/Auditは実装済（`src/ticket/models.py`, `src/interfaces/cli/board.py`, `src/persistence/audit.py`）。Spread watchはwarnで反映（`src/ticket/validators.py`, `pytest tests/unit/test_ticket_builder.py`）。GUI連携/監査統合テストも追加済。 |
| `EP-05 Weekly Review` | 0.6.3 実装優先度マトリクス（M1） | detailed_design_fx_signal_tool_v1.md:174 | done | 週次レポート/テンプレは実装済（`src/interfaces/cli/report.py`, `src/reporter/templates/weekly_m1_core.md`）。RiskDisclosure/Benchmark統合も完了済。Funding sync evidenceのRunbook表記を修正（`src/interfaces/cli/funding.py`）。 |
| `EP03-P4` | 22.5 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5508 | done | `RiskDisclosureService`拡張、状態更新/監査/ops_worklog/refresh_from_profileを追加済。 |
| `EP03-P5` | 22.5 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5509 | done | `tradectl compliance`拡張とRiskDisclosureロック/exit code/承認テストを追加済。 |
| `EP05-P2` | 22.5 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5510 | done | DataManifest/Validation Playbook同期のスタブ実装を追加済。 Other refs: 36.3 テスト & Codex Packet (detailed_design_fx_signal_tool_v1.md:6202, status done) |
| `EP04-P1` | 92.7 Codex Packet & テスト計画（EP04-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:10064 | done | TicketRecord v2とTicketBuilderは実装済（`src/ticket/models.py`, `src/ticket/builder.py`, `tests/unit/test_ticket_builder.py`）。 Other refs: 23.4 テスト & Codex Packet計画 (detailed_design_fx_signal_tool_v1.md:5586, status todo); 34.4 テスト & Codex Packet (detailed_design_fx_signal_tool_v1.md:6095, status todo) |
| `EP04-P2` | 92.7 Codex Packet & テスト計画（EP04-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:10065 | done | Board/Ticket CLI更新とSnapshotは実装済（`src/interfaces/cli/board.py`, `src/interfaces/cli/tickets.py`, `tests/approval/board/`）。 Other refs: 23.4 テスト & Codex Packet計画 (detailed_design_fx_signal_tool_v1.md:5587, status todo); 34.4 テスト & Codex Packet (detailed_design_fx_signal_tool_v1.md:6096, status todo) |
| `EP04-P3` | 92.7 Codex Packet & テスト計画（EP04-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:10066 | done | Audit Logger + GUI連携の統合テストを追加済。 Other refs: 23.4 テスト & Codex Packet計画 (detailed_design_fx_signal_tool_v1.md:5588, status done); 34.4 テスト & Codex Packet (detailed_design_fx_signal_tool_v1.md:6097, status done) |
| `EP04-P1` | 34.1 TradeJournalService | detailed_design_fx_signal_tool_v1.md:6029 | in_progress | TradeJournalService/CLIはJSONLベースの最小版のみ実装（`src/journal/service.py`, `src/interfaces/cli/__init__.py`）。SQLite/イベント連携/週次ハイライト生成は未実装。 |
| `EP03-P6` | 24.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5648 | done | LiquidityMonitorService + metrics/logging + GateState連携を実装（`src/risk/liquidity_monitor.py`, `metrics/liquidity_monitor.jsonl`, `snapshots/latest/liquidity_state.json`）。テスト: `pytest tests/unit/test_liquidity_monitor.py`. |
| `EP03-P7` | 24.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5649 | done | CLI `tradectl liquidity *` + Boardバナー + Ticket WARN統合 + Ops dashboard CLIを実装（`src/interfaces/cli/liquidity.py`, `src/interfaces/cli/board.py`, `src/ticket/builder.py`, `src/interfaces/cli/ops_dashboard.py`）。テスト: `pytest tests/unit/test_cli_liquidity.py tests/unit/test_ticket_builder.py tests/unit/test_ops_dashboard.py`. |
| `EP03-P8` | 24.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5650 | done | Emergency playbook stub + ops_worklog自動記録を追加（`src/ops/emergency.py`, `src/interfaces/cli/__init__.py`, `src/risk/liquidity_monitor.py`）。CLI: `tradectl emergency trigger --simulate --scenario liquidity_divergence`. |
| `EP05-P3` | 25.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5707 | done | Statementパーサ/設定テンプレ/単体テストを追加済（`src/reconciliation/statements.py`）。 Other refs: 36.3 テスト & Codex Packet (detailed_design_fx_signal_tool_v1.md:6203, status done) |
| `EP05-P4` | 25.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5708 | done | `tradectl reconcile statements/preview/scaffold`とCLI統合テストを追加済。 |
| `EP05-P5` | 25.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5709 | done | Validation Playbook同期（スタブ）を追加済。 |
| `EP06-P1` | 26.4 Codex Packet計画 & テレメトリ | detailed_design_fx_signal_tool_v1.md:5772 | todo | Other refs: 35.3 テスト & Codex Packet (detailed_design_fx_signal_tool_v1.md:6151, status todo) |
| `EP06-P2` | 26.4 Codex Packet計画 & テレメトリ | detailed_design_fx_signal_tool_v1.md:5773 | todo | Other refs: 35.3 テスト & Codex Packet (detailed_design_fx_signal_tool_v1.md:6152, status todo) |
| `EP06-P3` | 26.4 Codex Packet計画 & テレメトリ | detailed_design_fx_signal_tool_v1.md:5774 | todo |  |
| `EP05-P1` | 36.3 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6201 | in_progress | Benchmark compareは実装済（`src/reporter/benchmark.py`, `src/interfaces/cli/benchmark.py`, `pytest tests/unit/test_benchmark_comparator.py`）。Ingest/validateは未実装（CLIはstub）。 |
| `EP06-MR-P1` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6747 | todo |  |
| `EP06-MR-P2` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6748 | todo |  |
| `EP06-MR-P3` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6749 | todo |  |
| `EP06-MR-P4` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6750 | todo |  |
| `EP07-BO-P1` | 47.5 Codex Packet計画（BackOffice/Tax Track） | detailed_design_fx_signal_tool_v1.md:6841 | todo |  |
| `EP07-BO-P2` | 47.5 Codex Packet計画（BackOffice/Tax Track） | detailed_design_fx_signal_tool_v1.md:6842 | todo |  |
| `EP07-BO-P3` | 47.5 Codex Packet計画（BackOffice/Tax Track） | detailed_design_fx_signal_tool_v1.md:6843 | todo |  |
| `EP08-SS-P1` | 48.5 Codex Packet計画（Secure Sharing Track） | detailed_design_fx_signal_tool_v1.md:6914 | todo |  |
| `EP08-SS-P2` | 48.5 Codex Packet計画（Secure Sharing Track） | detailed_design_fx_signal_tool_v1.md:6915 | todo |  |
| `EP08-SS-P3` | 48.5 Codex Packet計画（Secure Sharing Track） | detailed_design_fx_signal_tool_v1.md:6916 | todo |  |
| `EP09-RTF-P1` | 49.4 Codex Packet計画（Real-time Feed Track） | detailed_design_fx_signal_tool_v1.md:6972 | todo |  |
| `EP09-RTF-P2` | 49.4 Codex Packet計画（Real-time Feed Track） | detailed_design_fx_signal_tool_v1.md:6973 | todo |  |
| `EP09-RTF-P3` | 49.4 Codex Packet計画（Real-time Feed Track） | detailed_design_fx_signal_tool_v1.md:6974 | todo |  |
| `EP09-LIC-P1` | 50.3 テスト & Codex Packet計画（Licensing Track） | detailed_design_fx_signal_tool_v1.md:7028 | todo |  |
| `EP09-LIC-P2` | 50.3 テスト & Codex Packet計画（Licensing Track） | detailed_design_fx_signal_tool_v1.md:7029 | todo |  |
| `EP09-LIC-P3` | 50.3 テスト & Codex Packet計画（Licensing Track） | detailed_design_fx_signal_tool_v1.md:7030 | todo |  |
| `EP10-ACC-P1` | 51.6 Codex Packet計画（Multi-Account Track） | detailed_design_fx_signal_tool_v1.md:7132 | todo |  |
| `EP10-ACC-P2` | 51.6 Codex Packet計画（Multi-Account Track） | detailed_design_fx_signal_tool_v1.md:7133 | todo |  |
| `EP10-ACC-P3` | 51.6 Codex Packet計画（Multi-Account Track） | detailed_design_fx_signal_tool_v1.md:7134 | todo |  |
| `EP11-OPS-P1` | 52.6 Codex Packet計画（Ops Automation Track） | detailed_design_fx_signal_tool_v1.md:7259 | done | OpsWorklogService query timezone fix + CLI `ops log add/list` (`src/ops/worklog.py`, `src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`); tests: `pytest tests/unit/test_ops_worklog_service.py tests/integration/test_ops_cli.py`. |
| `EP11-OPS-P2` | 52.6 Codex Packet計画（Ops Automation Track） | detailed_design_fx_signal_tool_v1.md:7260 | done | AutomationEffectTracker metrics/audit hooks + CLI `ops automation add` + report tool (`src/ops/automation.py`, `src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`, `tools/automation_effect_report.py`, `Makefile`); tests: `pytest tests/unit/test_automation_effect_tracker.py tests/integration/test_ops_automation_cli.py`. |
| `EP11-OPS-P3` | 52.6 Codex Packet計画（Ops Automation Track） | detailed_design_fx_signal_tool_v1.md:7261 | done | OpsAgenda CLI + metrics/audit logs + critical-first/runbook/validation pending logic + degraded_ack completion (`src/ops/agenda.py`, `src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`); tests: `pytest tests/integration/test_ops_agenda_cli.py tests/unit/test_ops_agenda_drills.py tests/unit/test_ops_agenda_status.py`. |
| `EP11-DRILL-P1` | 53.4 テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7342 | done | OpsDrillServiceのrunbook参照検証/レポート生成/metrics/events追加（`src/ops/drills.py`, `docs/templates/drill_report.md`）とユニットテスト追加（`pytest tests/unit/test_ops_drill_service.py`）。 |
| `EP11-DRILL-P2` | 53.4 テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7343 | done | Drill CLI helpers + Typer wiring (`src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`); tests: `pytest tests/unit/test_cli_ops_drills.py`. |
| `EP11-DRILL-P3` | 53.4 テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7344 | done | OpsAgenda drill pending/defer filtering + OpsEvidenceStore/AutomationEffect hooks (`src/ops/agenda.py`, `src/ops/evidence.py`, `src/ops/drills.py`); tests: `pytest tests/unit/test_ops_agenda_drills.py tests/unit/test_ops_evidence_store.py`. |
| `EP06-IDEA-P1` | 54.5 テスト戦略とCodex Packet | detailed_design_fx_signal_tool_v1.md:7436 | todo |  |
| `EP06-IDEA-P2` | 54.5 テスト戦略とCodex Packet | detailed_design_fx_signal_tool_v1.md:7437 | todo |  |
| `EP06-IDEA-P3` | 54.5 テスト戦略とCodex Packet | detailed_design_fx_signal_tool_v1.md:7438 | todo |  |
| `EP07-RSCH-P1` | 55.5 Codex Packet計画（Research Workspace Track） | detailed_design_fx_signal_tool_v1.md:7519 | todo |  |
| `EP07-RSCH-P2` | 55.5 Codex Packet計画（Research Workspace Track） | detailed_design_fx_signal_tool_v1.md:7520 | todo |  |
| `EP07-RSCH-P3` | 55.5 Codex Packet計画（Research Workspace Track） | detailed_design_fx_signal_tool_v1.md:7521 | todo |  |
| `EP09-BRD-P1` | 56.5 Codex Packet計画（Strategy Board Track） | detailed_design_fx_signal_tool_v1.md:7587 | todo |  |
| `EP09-BRD-P2` | 56.5 Codex Packet計画（Strategy Board Track） | detailed_design_fx_signal_tool_v1.md:7588 | todo |  |
| `EP09-BRD-P3` | 56.5 Codex Packet計画（Strategy Board Track） | detailed_design_fx_signal_tool_v1.md:7589 | todo |  |
| `EP09-LIFE-P1` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:7672 | todo |  |
| `EP09-LIFE-P2` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:7673 | todo |  |
| `EP09-LIFE-P3` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:7674 | todo |  |
| `EP12-DOC-P1` | 58.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7746 | todo |  |
| `EP12-DOC-P2` | 58.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7747 | todo |  |
| `EP12-DOC-P3` | 58.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7748 | todo |  |
| `EP12-DOC-P4` | 59.3 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7790 | todo |  |
| `EP12-DOC-P5` | 59.3 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7791 | todo |  |
| `EP13-SHADOW-P1` | 60.3 テレメトリ・テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7869 | todo |  |
| `EP13-SHADOW-P2` | 60.3 テレメトリ・テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7870 | todo |  |
| `EP13-SHADOW-P3` | 60.3 テレメトリ・テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7871 | todo |  |
| `EP10-COMP-P1` | 61.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:7960 | todo |  |
| `EP10-COMP-P2` | 61.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:7961 | todo |  |
| `EP10-COMP-P3` | 61.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:7962 | todo |  |
| `EP08-EXP-P1` | 62.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:8032 | todo |  |
| `EP08-EXP-P2` | 62.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:8033 | todo |  |
| `EP08-EXP-P3` | 62.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:8034 | todo |  |
| `EP11-INC-P1` | 63.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8102 | done | IncidentPostmortemService scaffold + template (`src/ops/postmortem.py`, `docs/templates/postmortem.md`); tests: `pytest tests/unit/test_incident_postmortem_service.py`. |
| `EP11-INC-P2` | 63.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8103 | done | TradeForensicsAnalyzer + ops incident CLI (`src/ops/trade_forensics.py`, `src/interfaces/cli/ops_incident.py`, `src/interfaces/cli/__init__.py`); tests: `pytest tests/unit/test_trade_forensics_analyzer.py tests/integration/test_ops_incident_cli.py`. |
| `EP11-INC-P3` | 63.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8104 | done | Postmortem metrics include detect/contain timings + evidence hash (`src/ops/postmortem.py`, min/max timeline bounds + non-negative clamp), validation playbook + RUN-INC-01 stub; tests: `pytest tests/unit/test_incident_postmortem_service.py`. |
| `EP12-STRESS-P1` | 64.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8164 | in_progress | Stress registry/engineとCLI実行の骨格あり（`src/stress/datasets.py`, `src/stress/engine.py`, `src/interfaces/cli/__init__.py`）。テレメトリ/監査/詳細集計は未実装。 |
| `EP12-STRESS-P2` | 64.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8165 | todo |  |
| `EP12-STRESS-P3` | 64.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8166 | todo |  |
| `EP13-COACH-P1` | 65.3 テレメトリ・ダッシュボード統合・Codex Packet | detailed_design_fx_signal_tool_v1.md:8223 | todo |  |
| `EP13-COACH-P2` | 65.3 テレメトリ・ダッシュボード統合・Codex Packet | detailed_design_fx_signal_tool_v1.md:8224 | todo |  |
| `EP13-COACH-P3` | 65.3 テレメトリ・ダッシュボード統合・Codex Packet | detailed_design_fx_signal_tool_v1.md:8225 | todo |  |
| `EP14-DEGRADE-P1` | 66.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8278 | todo |  |
| `EP14-DEGRADE-P2` | 66.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8279 | todo |  |
| `EP14-DEGRADE-P3` | 66.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8280 | todo |  |
| `EP11-RISKCONSENT-P1` | 67.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8357 | done | RiskDisclosureEnforcer core (`src/compliance/risk_disclosure_enforcer.py`); tests: `pytest tests/unit/test_risk_disclosure_enforcer.py`. |
| `EP11-RISKCONSENT-P2` | 67.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8358 | done | Device binding encrypted registry + CLI `compliance device`/`risk-disclosure enforce` with error exit on binding failure (`src/compliance/device_binding.py`, `src/interfaces/cli/compliance_risk.py`, `src/interfaces/cli/__init__.py`, `pyproject.toml`); tests: `pytest tests/unit/test_device_binding_service.py tests/integration/test_risk_consent_flow.py tests/unit/test_compliance_risk_cli.py`. |
| `EP11-RISKCONSENT-P3` | 67.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8359 | done | Risk consent metrics/audit include device_id/consent_reference_id + validation playbook updates (`metrics/risk_consent.jsonl`, `docs/validation_playbook/AC44_risk_consent.yaml`, `docs/runbooks/COMPLIANCE-01.md`); tests: `pytest tests/unit/test_risk_disclosure_enforcer.py`. |
| `EP12-PROMO-P1` | 68.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8422 | todo |  |
| `EP12-PROMO-P2` | 68.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8423 | todo |  |
| `EP12-PROMO-P3` | 68.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8424 | todo |  |
| `EP14-SUNSET-P1` | 69.4 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8505 | todo |  |
| `EP14-SUNSET-P2` | 69.4 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8506 | todo |  |
| `EP14-SUNSET-P3` | 69.4 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8507 | todo |  |
| `EP15-ACCESS-P1` | 70.4 Codex Packet・テスト・受入条件 | detailed_design_fx_signal_tool_v1.md:8575 | in_progress | Access review startはCLI/証跡出力を実装済（`src/interfaces/cli/access_review.py`, `src/interfaces/cli/__init__.py`）。レビュー完了/承認/ポリシー突合は未実装。 |
| `EP15-ACCESS-P2` | 70.4 Codex Packet・テスト・受入条件 | detailed_design_fx_signal_tool_v1.md:8576 | todo |  |
| `EP15-ACCESS-P3` | 70.4 Codex Packet・テスト・受入条件 | detailed_design_fx_signal_tool_v1.md:8577 | todo |  |
| `EP16-REG-P1` | 78.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:8738 | todo |  |
| `EP16-REG-P2` | 78.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:8739 | todo |  |
| `EP16-REG-P3` | 78.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:8740 | todo |  |
| `EP17-BROKER-P1` | 79.4 Runbook・Feature Flag・受入テスト | detailed_design_fx_signal_tool_v1.md:8778 | todo |  |
| `EP17-BROKER-P2` | 79.4 Runbook・Feature Flag・受入テスト | detailed_design_fx_signal_tool_v1.md:8779 | todo |  |
| `EP17-BROKER-P3` | 79.4 Runbook・Feature Flag・受入テスト | detailed_design_fx_signal_tool_v1.md:8780 | todo |  |
| `EP17-BROKER-P4` | 80.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8929 | todo |  |
| `EP17-BROKER-P5` | 80.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8930 | todo |  |
| `EP17-BROKER-P6` | 80.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8931 | todo |  |
| `EP17-BROKER-P7` | 81.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8990 | todo |  |
| `EP17-BROKER-P8` | 81.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8991 | todo |  |
| `EP17-BROKER-P9` | 81.6 Codex実装パケット | detailed_design_fx_signal_tool_v1.md:8992 | todo |  |
| `EP17-BROKER-P10` | 82.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9058 | todo |  |
| `EP17-BROKER-P11` | 82.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9059 | todo |  |
| `EP17-BROKER-P12` | 82.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9060 | todo |  |
| `EP17-BROKER-P13` | 83.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9110 | todo |  |
| `EP17-BROKER-P14` | 83.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9111 | todo |  |
| `EP17-BROKER-P15` | 83.5 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9112 | todo |  |
| `EP17-BROKER-P16` | 84.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9257 | todo |  |
| `EP17-BROKER-P17` | 84.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9258 | todo |  |
| `EP17-BROKER-P18` | 84.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9259 | todo |  |
| `EP17-BROKER-P19` | 85.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9314 | todo |  |
| `EP17-BROKER-P20` | 85.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9315 | todo |  |
| `EP17-BROKER-P21` | 85.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9316 | todo |  |
| `EP18-GUI-P1` | 86.5 Codex実装パケットとテスト計画 | detailed_design_fx_signal_tool_v1.md:9392 | todo |  |
| `EP18-GUI-P2` | 86.5 Codex実装パケットとテスト計画 | detailed_design_fx_signal_tool_v1.md:9393 | todo |  |
| `EP18-GUI-P3` | 86.5 Codex実装パケットとテスト計画 | detailed_design_fx_signal_tool_v1.md:9394 | todo |  |
| `EP20-SHADOW-GW-P1` | 87.3 Codexテスト指針とFeature Flag運用 | detailed_design_fx_signal_tool_v1.md:9474 | todo |  |
| `EP20-SHADOW-GW-P2` | 87.3 Codexテスト指針とFeature Flag運用 | detailed_design_fx_signal_tool_v1.md:9475 | todo |  |
| `EP20-SHADOW-GW-P3` | 87.3 Codexテスト指針とFeature Flag運用 | detailed_design_fx_signal_tool_v1.md:9476 | todo |  |
| `EP21-ALPHA-P1` | 88.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9624 | todo |  |
| `EP21-ALPHA-P2` | 88.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9625 | todo |  |
| `EP21-ALPHA-P3` | 88.6 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:9626 | todo |  |
| `EP01-P1` | 89.5 Codex Packet & テスト計画（EP01-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9706 | done | `FallbackRetryTask`イベント化を実装済（`src/data/fallback.py`, `src/data/service.py`, `tests/unit/test_data_ingestion_delays.py`）。 |
| `EP01-P2` | 89.5 Codex Packet & テスト計画（EP01-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9707 | done | `ManualCsvReconciler`/監査ログを実装済（`src/data/manual_csv.py`, `src/interfaces/cli/data.py`, `tests/unit/test_manual_csv_reconciler.py`）。 |
| `EP01-P3` | 89.5 Codex Packet & テスト計画（EP01-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9708 | done | Resync CLI/Evidence/`health.suggest_resume`は実装済（`src/interfaces/cli/resync.py`）。`tools/sla_report.py`/`make sla-report`を実装済。Resync進捗テーブルはCLIに反映済。証跡: `logs/resync/resync_events.jsonl`, `metrics/data_ingestion_sla.jsonl`, `reports/validation_log/AC-04_20251117.md`, `reports/validation_log/resync_failover_20260108.json`, `reports/ops/resync/20260112T092627.665111Z.md`。CLIは`session`未注入で`status=unavailable`扱い。テスト: `pytest tests/unit/test_cli_resync.py`。 |
| `EP03-P1` | 90.6 Codex Packet & テスト計画（EP03-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9864 | done | `HealthMonitor`のアクションキューと監査ログを実装済（`src/core/health.py`, `src/interfaces/cli/status.py`, `tests/unit/test_health_state.py`）。 |
| `EP03-P2` | 90.6 Codex Packet & テスト計画（EP03-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9865 | done | Spread/NTP/News統合とCLIを実装済（`src/execution/spread.py`, `src/interfaces/cli/spread.py`, `tests/unit/test_spread_monitor.py`）。 |
| `EP03-P3` | 90.6 Codex Packet & テスト計画（EP03-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9866 | done | Kill Switch/Board連携は実装済（`src/interfaces/cli/kill_switch.py`, `src/risk/manager.py`, `tests/cli/test_tradectl_board_kill_switch.py`）。 |
| `EP02-P1` | 91.7 Codex Packet & テスト計画（EP02-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9941 | done | Feature determinism/キャッシュキー/バージョニング実装済（`src/features/pipeline.py`, `src/features/cache.py`, `tests/unit/test_feature_pipeline_determinism.py`）。 |
| `EP02-P2` | 91.7 Codex Packet & テスト計画（EP02-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9942 | done | `board_diagnostics` CLIを実装済（`src/interfaces/cli/board_diagnostics.py`, `tests/cli/test_board_diagnostics.py`）。 |
| `EP02-P3` | 91.7 Codex Packet & テスト計画（EP02-P1/P2/P3） | detailed_design_fx_signal_tool_v1.md:9943 | done | Execution determinism/Replay CLIは実装済（`src/execution/model.py`, `src/interfaces/cli/determinism.py`）。Replay diff_countは戦略単位で集計（`pytest tests/unit/test_diagnostics_determinism.py`）。証跡: `metrics/replay_jobs.jsonl`。 |
| `EP-00 Config Foundations` | 12.1 Packetバックログ概要 | detailed_design_fx_signal_tool_v1.md:4023 | done | `make config-init`/`schema-validate`/`config/README.md`/`tradectl config ls`整備は完了済。 |
| `EP00-P1` | 12.1 Packetバックログ概要 | detailed_design_fx_signal_tool_v1.md:4023 | done | `make config-init`/`schema-validate`/`config/README.md`/`tradectl config ls`整備は完了済。 |
| `EP01-T1` | 15.1 EP-01 DataLag Mitigation（データSLA） | detailed_design_fx_signal_tool_v1.md:4520 | done | provider優先度のper_symbol override/`FallbackRetryTask`キュー連携/`data.fetch`ログを実装済。 |
| `EP01-T2` | 15.1 EP-01 DataLag Mitigation（データSLA） | detailed_design_fx_signal_tool_v1.md:4521 | done | NTPドリフト・欠損比率評価と`DataLatencyAlert`追加、Manual CSVブロック条件をprimary限定で整備。 |
| `EP01-T3` | 15.1 EP-01 DataLag Mitigation（データSLA） | detailed_design_fx_signal_tool_v1.md:4522 | done | Resync failover report表形式/`health.suggest_resume`連携を実装済。 |
| `EP02-T1` | 15.2 EP-02 Strategy Determinism（シグナル決定論） | detailed_design_fx_signal_tool_v1.md:4533 | done | FeaturePipeline RNG決定論化は実装済、証跡: `metrics/feature_cache.jsonl`。 |
| `EP02-T2` | 15.2 EP-02 Strategy Determinism（シグナル決定論） | detailed_design_fx_signal_tool_v1.md:4534 | done | `strategy.determinism`イベント出力と`tradectl board --view diagnostics`対応済。 |
| `EP02-T3` | 15.2 EP-02 Strategy Determinism（シグナル決定論） | detailed_design_fx_signal_tool_v1.md:4535 | done | Human delay三角分布/seed_offset設定とPaper/Live丸めを実装済。 |
| `EP03-T1` | 15.3 EP-03 Guardrails（リスク/ヘルス） | detailed_design_fx_signal_tool_v1.md:4544 | done | Health action監査ログ強化と`auto_ack_required`をkill switch stateへ追加済。 |
| `EP03-T2` | 15.3 EP-03 Guardrails（リスク/ヘルス） | detailed_design_fx_signal_tool_v1.md:4545 | done | `cooldown_reason`と`metrics/network.jsonl`滞留時間ログをSpreadMonitorへ実装済。 |
| `EP03-T3` | 15.3 EP-03 Guardrails（リスク/ヘルス） | detailed_design_fx_signal_tool_v1.md:4546 | done | reduce_only推奨フックをRiskManagerへ追加済。 |
| `EP04-T1` | 15.4 EP-04 Ticket Clarity（HITL UX） | detailed_design_fx_signal_tool_v1.md:4555 | done | TicketBuilderの構造化/TTL委譲を反映済み。 |
| `EP04-T2` | 15.4 EP-04 Ticket Clarity（HITL UX） | detailed_design_fx_signal_tool_v1.md:4556 | done | Boardバナー表示と承認確認ダイアログを追加済み。 |
| `EP04-T3` | 15.4 EP-04 Ticket Clarity（HITL UX） | detailed_design_fx_signal_tool_v1.md:4557 | done | 監査delta/consent_reference_id/health/spread情報 + determinism hashの明示指定 + risk_disclosure/二重承認の整合を反映済み。 |
| `EP05-T1` | 15.5 EP-05 Weekly Review（レポート/監査） | detailed_design_fx_signal_tool_v1.md:4566 | done | 週次テンプレへManual CSV/RiskSummary/ops_worklogを統合済み。 |
| `EP05-T2` | 15.5 EP-05 Weekly Review（レポート/監査） | detailed_design_fx_signal_tool_v1.md:4567 | done | Benchmark欠損率判定と`benchmark_gap`イベントを実装済み。 |
| `EP05-T3` | 15.5 EP-05 Weekly Review（レポート/監査） | detailed_design_fx_signal_tool_v1.md:4568 | done | 週次テンプレに署名欄/Manual CSV/Guardrails節を追加済み。 |
| `EP04-P4` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5878 | todo |  |
| `EP05-P6` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5840 | todo |  |
| `EP05-P7` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5926 | todo |  |
| `EP06-P4` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5805 | todo |  |
| `EP06-P5` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5990 | todo |  |
| `EP07-P1` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5967 | todo |  |
| `EP07-P2` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:6018 | todo |  |
