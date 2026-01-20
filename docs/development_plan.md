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
- 2026-01-15T09:53Z — EP03 review fixes: gate_state liquidity optional, liquidity ingest window option, ops dashboard missing-gap threshold
- 2026-01-15T10:21Z — EP04-P1: implement TradeJournalService SQLite-backed journal, metrics, and tests
- 2026-01-15T10:23Z — EP04-P1: refine TradeJournalService audit/metrics outputs and update tests
- 2026-01-15T11:27Z — EP04-P1 fixes: preserve entry_id on upsert, UUIDv7 ids, daily audit log path
- 2026-01-15T11:53Z — EP04-P2: add journal CLI commands, feature flags, and report gating; tests added
- 2026-01-15T12:01Z — EP04-P1/P2 follow-up: fix UUIDv7 variant bits, journal stats tz handling, and CLI tag defaults
- 2026-01-15T12:18Z — EP04-P3: add journal runbook, validation playbook entry, and changelog
- 2026-01-15T12:23Z — EP04-P3 follow-up: fix UUIDv7 variant bits, template AC37 journal, add flag enable steps to runbook
- 2026-01-16T12:50Z — EP05-P1: implement benchmark ingest/manual validation and add unit tests
- 2026-01-16T13:01Z — EP05-P1 follow-up: avoid ingest output collisions and pair manual validation files
- 2026-01-16T13:10Z — EP05-P2: add BenchmarkReplayService, CLI compare update, and replay tests
- 2026-01-16T13:13Z — EP05-P2 fixes: separate benchmark export formats and avoid output collisions
- 2026-01-16T13:18Z — EP05-P3: add benchmark summary block, feature flags, runbook, and report test
- 2026-01-16T13:41Z — EP05-P2/P3 follow-up: benchmark path discovery and provider hint in weekly summary
- 2026-01-17T00:03Z — EP06-P1/P2: add parameter drift monitor config/schema updates, research drift CLI, runbook, and tests
- 2026-01-17T00:05Z — EP06-P2 follow-up: add health-state override for drift CLI and refresh drift tests
- 2026-01-17T00:13Z — EP06-P1/P2 review fixes: suppress cleared event on missing drift inputs; update drift runbook refs
- 2026-01-17T00:23Z — RUN-DRIFT-01: assign AC-47 and update validation log reference
- 2026-01-17T00:27Z — Log EP06-P3 dependency clarification in Codex Q&A
- 2026-01-17T00:30Z — Reconcile EP06 backlog: restore EP06-P1/P2 to IdeaRegistry/ResearchPipeline; track drift under EP35-DRIFT
- 2026-01-17T01:27Z — EP06-P1/P2: add IdeaRegistry/ResearchPipeline CLI, validation suite, runbook, and tests
- 2026-01-17T01:38Z — Review fixes: add research manifest CLI, adjust RES-IDEA-01 AC placeholder, and keep YAML JSON fallback
- 2026-01-17T01:41Z — Review fixes: add research manifest CLI coverage, JSON fallback parse for yaml.py, and manifest CLI test
- 2026-01-17T01:45Z — EP06-P3: add research promotion workflow CLI, audit/event logs, and AC46 playbook
- 2026-01-17T02:09Z — EP06-P4/P5: add strategy manifest validation/renewal + scoring + board integration; tests: pytest tests/unit/test_strategy_manifest_validator.py tests/unit/test_strategy_scoring.py tests/integration/test_strategy_manifest_cli.py tests/integration/test_board_scores.py
- 2026-01-17T02:53Z — EP06-P4: add research manifest link + risk band evaluation; update strategy manifest entries, runbook RES-MANIFEST-01 v0.2, tests: pytest tests/unit/test_strategy_manifest_validator.py tests/integration/test_strategy_manifest_cli.py
- 2026-01-17T03:19Z — Fix review findings: move strategy parameters to correct level, add validation_playbook_id to research manifests, cache per-manifest dataset checks; tests: pytest tests/unit/test_strategy_manifest_validator.py tests/integration/test_strategy_manifest_cli.py
- 2026-01-17T05:14Z — Add AC-01 validation playbook and record CLI verification for research manifest/strategy manifest
- 2026-01-17T05:22Z — EP04-P4: add account aggregator + accounts CLI (status/ingest/aggregate/alerts) and tests; CLI checked
- 2026-01-17T05:31Z — Fix accounts aggregator: derive open_positions from positions list and honor tz for naive timestamps; tests: pytest tests/unit/test_account_aggregator.py tests/integration/test_accounts_cli.py
- 2026-01-17T07:38Z — EP05-P6: add attribution engine + weekly report integration; tests: pytest tests/unit/test_attribution_engine.py tests/integration/test_weekly_report_attribution.py
- 2026-01-17T07:43Z — EP05-P6 review fixes: attribution template for extended blocks, avoid double headers, deterministic approval snapshot; tests: pytest tests/unit/test_attribution_engine.py tests/integration/test_weekly_report_attribution.py tests/approval/test_weekly_attribution_snapshot.py
- 2026-01-17T08:16Z — EP05-P7: add audit bundle hash/signature, report output, metrics logging, CLI payload, and tests
- 2026-01-17T11:39Z — EP05-P7 review fixes: sign audit_manifest SHA, suppress dry-run metrics/events, rename verify timing field
- 2026-01-17T11:43Z — EP05-P7: verified audit bundle dry-run CLI output (missing signals noted)
- 2026-01-17T11:46Z — EP07-P1: release gate metrics/audit/events, dry-run support, and release CLI tests
- 2026-01-17T11:58Z — EP07-P1 audit log uses release audit schema logger; tests updated
- 2026-01-17T12:07Z — EP07-P2: add OpsReadinessService with metrics/alerts/reporting and CLI integration
- 2026-01-17T12:12Z — EP07-P2: captured ops readiness CLI evidence (missing backups/incidents)
- 2026-01-17T12:18Z — Captured evidence for ops readiness, audit bundle, and release gate CLI flows
- 2026-01-17T12:21Z — EP06-MR-P1: add model risk register service, markdown template, and loader test
- 2026-01-17T12:38Z — EP06-MR-P2..P4: add model risk artifact manifest + CLI + weekly summary, update templates, add CLI tests; tests: pytest tests/unit/test_model_risk_cli.py tests/unit/test_model_risk_artifacts.py tests/unit/test_model_risk_register.py tests/unit/test_cli_report.py
- 2026-01-17T13:01Z — EP06-IDEA-P1..P3: implement IdeaPipelineManager + checklists/config/schema, research idea CLI (show/checklist-update/evidence-bundle/report), idea pipeline report template, ops agenda/readiness integration, secure share stub + GOV-IDEA-01; tests: pytest tests/unit/test_idea_pipeline_manager.py tests/integration/test_research_idea_cli.py tests/unit/test_ops_agenda_status.py
- 2026-01-17T13:35Z — EP06 review fixes: target-stage validation in IdeaPipelineManager, feature-flag gating for idea CLI + ops agenda, ops readiness missing idea_pipeline detection, added ops readiness evaluator test; tests: pytest tests/unit/test_idea_pipeline_manager.py tests/integration/test_research_idea_cli.py tests/unit/test_ops_readiness_evaluator.py tests/unit/test_ops_agenda_status.py
- 2026-01-17T13:57Z — EP06 review fixes: update idea index current_stage on transition, gate idea pipeline scoring/agenda by feature flag, add public load methods; tests: pytest tests/unit/test_idea_pipeline_manager.py tests/integration/test_research_idea_cli.py tests/unit/test_ops_readiness_evaluator.py tests/unit/test_ops_agenda_status.py
- 2026-01-17T14:12Z — EP07-BO-P1: add backoffice ledger snapshot + finance ledger CLI; tests: pytest tests/unit/test_backoffice_ledger.py
- 2026-01-17T14:19Z — EP07-BO-P1 review fixes: default feature flag profile to mode, skip mode-missing events for non-live, period-scoped JSONL; tests: pytest tests/unit/test_backoffice_ledger.py
- 2026-01-17T14:40Z — EP07 complete: add tax report generator/CLI, finance audit bundle integration, research workspace/notebook/artifacts; runbook RUN-TAX-01 v1.2; tests: pytest tests/unit/test_backoffice_ledger.py tests/unit/test_tax_report_generator.py tests/integration/test_finance_cli.py tests/unit/test_research_workspace_manager.py tests/integration/test_research_notebook_cli.py tests/unit/test_research_artifact_registry.py tests/integration/test_research_data_sync.py tests/integration/test_audit_bundle_cli.py
- 2026-01-17T14:42Z — Fix research notebook CLI test isolation; rerun: pytest tests/integration/test_research_notebook_cli.py
- 2026-01-17T14:42Z — Tax report totals adjustment guard; rerun: pytest tests/unit/test_tax_report_generator.py
- 2026-01-17T14:56Z — EP07 review fixes: tax report template formatting + fee writeoff scenario, notebook execute error when jupyter missing, finance adjustments require signature, audit manifest duplicate guard; tests: pytest tests/unit/test_tax_report_generator.py tests/integration/test_research_notebook_cli.py
- 2026-01-17T15:10Z — EP08-SS-P1..P3 secure share: fix manifest serialization, add tests for secure share + publisher + finance share CLI (pytest tests/unit/test_secure_share_service.py tests/unit/test_evidence_bundle_publisher.py tests/integration/test_finance_share_cli.py)
- 2026-01-17T15:14Z — SecureShare review fixes: archive paths preserve repo-relative structure, error on missing files, manifest path matching uses resolved paths; tests: pytest tests/unit/test_secure_share_service.py tests/unit/test_evidence_bundle_publisher.py tests/integration/test_finance_share_cli.py
- 2026-01-18T02:09Z — EP09 completed: real-time feed evaluator+CLI/runbook, licensing registry+CLI/runbook, strategy board+lifecyle governance; tests: pytest tests/unit/test_real_time_feed_evaluator.py tests/cli/test_tradectl_feed_eval.py tests/integration/test_feed_eval_shadow.py tests/unit/test_license_registry.py tests/integration/test_licensing_cli.py tests/integration/test_feed_eval_with_license.py tests/unit/test_strategy_board_service.py tests/integration/test_strategy_board_cli.py tests/unit/test_strategy_lifecycle_orchestrator.py tests/integration/test_lifecycle_cli.py
- 2026-01-18T02:10Z — Strategy board review fix: decisions log respects output_dir; tests: pytest tests/unit/test_strategy_board_service.py tests/integration/test_strategy_board_cli.py tests/unit/test_strategy_lifecycle_orchestrator.py tests/integration/test_lifecycle_cli.py
- 2026-01-18T02:31Z — EP10-ACC-P1: account aggregation base + CLI aggregate/diff + portfolio state template; tests: pytest tests/unit/test_account_aggregator.py tests/integration/test_accounts_cli.py
- 2026-01-18T02:34Z — Account aggregation review fixes: PositionRecord serialization, broker field lookup, statement_path required, diff total_margin fallback; tests: pytest tests/unit/test_account_aggregator.py tests/integration/test_accounts_cli.py
- 2026-01-18T02:39Z — EP10-ACC-P2/P3: portfolio exposure analyzer + variance thresholds, account coverage/rebalance CLI, runbook/playbook; tests: pytest tests/unit/test_portfolio_exposure_analyzer.py tests/integration/test_account_rebalance_cli.py
- 2026-01-18T02:48Z — Fix account aggregation variance detection mapping and add unit test
- 2026-01-18T02:50Z — Re-ran EP10 account exposure analyzer + rebalance CLI tests
- 2026-01-18T03:02Z — EP12-DOC-P1: add docops registry/runbook inventory, doclint/check-runbooks, and docs runbook CLI
- 2026-01-18T03:05Z — DocOps: avoid emitting review events during no-write inventory refresh
- 2026-01-18T03:25Z — EP12-DOC-P2: add decision journal and onboarding services + CLI
- 2026-01-18T03:43Z — DocOps: append onboarding completion to AC16 playbook and skip report on dry-run
- 2026-01-18T03:45Z — EP12-DOC-P3: add docops exporter and docs export CLI
- 2026-01-18T04:01Z — EP12-DOC-P4/P5: add docbuild pipeline + docs build/diff/lint commands and doclint UX checks
- 2026-01-18T04:06Z — DocBuild: implement docs serve support in docbuild tool and CLI
- 2026-01-18T04:06Z — Fix docbuild CLI serve dispatch
- 2026-01-18T04:28Z — EP12-STRESS: fix stress audit bundle serialization + YAML fallback, add risk stress CLI tests; tests: pytest tests/unit/test_margin_stress_lab.py tests/unit/test_stress_simulation.py tests/unit/test_risk_stress_cli.py
- 2026-01-18T05:36Z — EP12-STRESS: align report stamp to UTC and serialize envelopes with safe_dump JSON fallback; tests: pytest tests/unit/test_risk_stress_cli.py tests/unit/test_margin_stress_lab.py tests/unit/test_stress_simulation.py
- 2026-01-18T05:46Z — EP12-PROMO-P1: add PromotionChecklistService core + experiment loader stub + manual review handling; tests: pytest tests/unit/test_promotion_checklist.py
- 2026-01-18T05:51Z — EP12-PROMO-P1 review fixes: align idea root to research/ideas and skip validation items in stage checklist; tests: pytest tests/unit/test_promotion_checklist.py
- 2026-01-18T05:58Z — EP12-PROMO-P2: add promote/checklist/simulate CLI integration and tests; tests: pytest tests/unit/test_research_promote_cli.py
- 2026-01-18T10:22Z — EP12-PROMO-P2 review fix: relax promote callback required options so subcommands parse correctly; tests: pytest tests/unit/test_research_promote_cli.py
- 2026-01-18T11:04Z — EP12-PROMO-P3: add promotion gate metrics/evidence/validation/ops agenda hooks; tests: pytest tests/unit/test_promotion_gate_metrics.py
- 2026-01-18T11:07Z — EP12-PROMO-P3 review fix: OpsEvidenceStore writes non-drill playbooks without _drill suffix; tests: pytest tests/unit/test_promotion_gate_metrics.py tests/unit/test_research_promote_cli.py
- 2026-01-18T11:11Z — EP13-SHADOW-P1: add ShadowStateStore + ShadowSessionOrchestrator scaffold; tests: pytest tests/unit/test_shadow_state_store.py tests/unit/test_shadow_session_orchestrator.py
- 2026-01-18T11:12Z — EP13-SHADOW-P1 review fix: shadow event log now JSONL and event_id uses microsecond precision; tests: pytest tests/unit/test_shadow_state_store.py tests/unit/test_shadow_session_orchestrator.py
- 2026-01-18T12:31Z — EP13 Shadow/Coaching: Slack bridge+GUI API, coaching telemetry/CLI/dashboard+report integration, runbooks/playbook, tests
- 2026-01-18T12:34Z — EP13 coaching tuning: fix priority scoring and add AC10 to validation index; rerun coaching/telemetry tests
- 2026-01-18T12:53Z — EP13 Shadow review fix: replay writes to shadow_replay.jsonl to avoid duplicating source event log
- 2026-01-18T13:53Z — Re-ran EP10 ACC/COMP tests (pytest tests/unit/test_account_aggregator.py tests/integration/test_accounts_cli.py tests/unit/test_portfolio_exposure_analyzer.py tests/integration/test_account_rebalance_cli.py tests/unit/test_ticket_scenario_generator.py tests/unit/test_compliance_regression_runner.py tests/integration/test_compliance_regression_cli.py)
- 2026-01-18T14:13Z — EP08-EXP: add experiment tracker/scheduler/CLI, validation playbook + runbook; tests: pytest tests/unit/test_experiment_tracker.py tests/integration/test_research_experiment_cli.py tests/unit/test_promotion_checklist.py tests/unit/test_promotion_gate_metrics.py
- 2026-01-18T14:16Z — EP08-EXP review fix: avoid implicit completion when no metrics/--complete; tests: pytest tests/unit/test_experiment_tracker.py tests/integration/test_research_experiment_cli.py
- 2026-01-18T20:32Z — Validation check attempted: make check-validation (missing Make target)
- 2026-01-18T20:48Z — Add check-validation target and normalize AC43_postmortem entries; ran make check-validation
- 2026-01-18T21:29Z — Complete EP14 degradation/sunset workflows with CLI wiring, runbook/playbook updates, and tests
- 2026-01-19T11:33Z — Ran make check-validation after EP14 playbook additions
- 2026-01-19T11:37Z — EP14 review fixes: guard unknown degradation scenarios, enforce evidence presence, default sunset/degradation playbook categories; reran EP14 tests
- 2026-01-19T11:40Z — EP14 refactor: enforce evidence existence in sunset, normalize playbook payloads, add missing-evidence test; reran EP14 tests
- 2026-01-19T12:26Z — M1 review fix: select bridge fallback metrics by strategy_id for hands-off sizing; added tests
- 2026-01-19T12:55Z — EP15 access governance CLI/service wiring, agenda tasks, validation/runbook updates
- 2026-01-19T13:07Z — EP15 access checks: ops agenda status tests pass, validation playbook category check, critical_first cutoff uses target_date
- 2026-01-20T10:23Z — EP15 access review fixes: deterministic enforcement device selection, quarantine reason block, evidence validation handling
- 2026-01-20T10:31Z — EP15 access review hardening: validate evidence before completion, surface missing due_at in ops agenda
- 2026-01-20T10:36Z — EP15 tests: access_governance selector empty, ops_agenda_status passes
- 2026-01-20T11:09Z — EP16 regression backtest suite/CLI/CI/playbook/runbook implemented; regression tests + validation check executed
- 2026-01-20T11:26Z — EP16 regression backtest review fixes: error on empty scenarios + config error handling

## Codex Q&A Log
When Codex asks a clarifying question, track it here instead of `docs/prompt_packages/` (legacy).
Default SLA: 6 hours unless otherwise specified.

| Logged (UTC) | Question | SLA | Response Summary | Design References | Status |
| --- | --- | --- | --- | --- | --- |
| 2026-01-12T12:05Z | 「質問関係」の対象機能を確認。 | 6h | 推奨設定で進行し、設計準拠で質問対応プロトコルを`docs/development_plan.md`に集約。 | `detailed_design_fx_signal_tool_v1.md` §12.3.5 | closed |
| 2026-01-17T00:26Z | EP06-P3の昇格自動化はEP06-P1/P2（IdeaRegistry/ResearchPipeline）未実装のため、最小スコープで`promote`をスタブ化するか、P1/P2相当の土台まで実装して進めるか確認したい。 | 6h | EP06-P1/P2（IdeaRegistry/ResearchPipeline）を先に実装して進行。 | `detailed_design_fx_signal_tool_v1.md` §26.2-§26.4 | closed |
| 2026-01-17T03:18Z | Strategy manifestの`parameters`配置とResearchManifestの`validation_playbook_id`追加方針を確認。 | 6h | `parameters`はStrategyEntry直下へ修正し、ResearchManifestに`validation_playbook_id`を追加して照合可能にする。 | `detailed_design_fx_signal_tool_v1.md` §27.1/§26.1 | closed |

## Current Status Snapshot (2026-01-12)
- M1 quality checklist: complete.
- M1 core gaps: weekly report risk summary/extended blocks implemented; remaining work is M1.1+ governance/drills/docs.
- M2+ scaffolds detected: stress registry/engine, TradeJournalService now SQLite-backed with weekly summary/metrics, benchmark compare exist but are partial.
- M3+ partials: risk consent completed; access review start scaffolded; licensing/board/lifecycle/compliance governance mostly todo.
- Design EP coverage check: EP IDs (EP-XX vs EPXX) normalized; backlog coverage matches design EP list.
- Design Alignment Backlog totals: 167 entries (done 56 / in_progress 0 / todo 111).
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
| M1 Core: Ticket/HITL | M1 | Done | `src/ticket/builder.py`, `src/ticket/validators.py`, `src/interfaces/cli/tickets.py`; review fixes: spread watch marks checklist warn + determinism hash preserved + gate-state double-entry enforcement + risk_disclosure status normalization + fallback metrics select by strategy_id; tests: `pytest tests/unit/test_ticket_builder.py tests/unit/test_ticket_builder_gate_state.py tests/unit/test_cli_ticket_actions.py tests/unit/test_ticket_builder_hands_off.py` | None. |
| M1 Core: Mode switching | M1 | Done | `src/core/session.py`, `src/interfaces/cli/session.py`; review fix ensures log path checked before start and manager stop on failure; tests: `pytest tests/cli/test_session_cli.py` | None. |
| M1 Core: Weekly report | M1 | Done | `src/interfaces/cli/report.py`, template; review fix: metric state supports CSV KPI sources; tests: `pytest tests/unit/test_cli_report.py` | Extended blocks are enabled in M1.1. |
| M1 Core: Resync & snapshot | M1 | Done | `src/core/resync.py`, `src/interfaces/cli/resync.py`, `src/core/snapshot.py`; review fixes: snapshot timestamps are UTC-aware + resync returns unavailable when session missing + catch-up lag 30m maps to degraded; tests: `pytest tests/unit/test_event_bus_snapshot_placeholder.py tests/unit/core/test_event_bus_snapshot_scaffold.py tests/unit/test_cli_resync.py`; ops evidence: `reports/ops/resync/20260112T092627.665111Z.md` | None. |
| M1 Core: Funding service | M1 | Done | `src/funding/service.py`, `src/interfaces/cli/funding.py`; review fixes: runbook reference corrected + numeric formatting normalization; tests: `pytest tests/cli/test_funding_cli.py` | None. |
| M1.1+ Provider integrations | M1.1+ | Done | Provider profiles (`config/provider_profiles/local.yaml`), paid feed adapter (`src/data/providers/paid_feed.py`), config scaffold (`config/data_sources/paid_feed.yaml`), service wiring (`src/data/service.py`); tests: `pytest tests/unit/test_data_service_sla.py tests/unit/test_data_service_backfill.py tests/config/test_config_schema_smoke.py` | None. |
| M1.1+ Weekly report extended blocks | M1.1+ | Done | `RiskSummary` summary from risk policy/logs, extended blocks wired in `src/interfaces/cli/report.py`; tests: `pytest tests/unit/test_cli_report.py` | None. |
| M1.1+ Audit bundle | M1.1+ | Done | AuditBundleService signs manifest SHA, emits report + metrics, and CLI output (`src/audit/bundle.py`, `src/interfaces/cli/__init__.py`), report at `reports/audit/audit_pack/<period>.md`, metrics at `metrics/audit_bundle.jsonl`; tests: `pytest tests/unit/test_audit_bundle.py tests/integration/test_audit_bundle_cli.py`. Design cross-check: §30.0-§30.2. | None. |
| M1.1+ Release gate | M1.1+ | Done | ReleaseGateService generates checklist, records results, verifies blocking with guardrails metrics + audit log, and supports dry-run (`src/release/gate.py`, `src/interfaces/cli/__init__.py`), metrics at `metrics/release_gate.jsonl`, audit log at `logs/audit/release_<YYYYMMDD>.jsonl` validated by `docs/schemas/release_audit.schema.json`; tests: `pytest tests/unit/test_release_gate_service.py tests/integration/test_release_cli.py`. Design cross-check: §31.0-§31.2. | None. |
| M2+ Ops readiness | M2+ | Done | OpsReadinessService + CLI/metrics/report integration (`src/ops/readiness.py`, `src/interfaces/cli/ops.py`), metrics at `metrics/ops_readiness.jsonl`; tests: `pytest tests/unit/test_ops_readiness_service.py tests/integration/test_ops_readiness_cli.py`. Design cross-check: §33.1/§33.3. | None. |
| M2+ Shadow bridge & GUI API | M2+ | Done | SlackShadowBridge + shadow CLI (test/replay/status/serve) + GUI API helpers (`src/interfaces/shadow/slack_bridge.py`, `src/interfaces/cli/shadow.py`, `src/interfaces/gui/shadow_api.py`), replay log separated to avoid re-appending to source event log. Feature flag `shadow.slack_enabled` + runbooks (`docs/runbooks/RUN-SHADOW-01.md`, `docs/runbooks/RUN-SHADOW-02.md`). Tests: `pytest tests/unit/test_slack_shadow_bridge.py tests/unit/test_shadow_gui_api.py`. Design cross-check: §60.1/§60.2. | None. |
| M2+ Coaching telemetry & playbook | M2+ | Done | TraderWorkflowTelemetryService + CoachingPlaybook + ops coaching CLI + dashboard/report integration (`src/telemetry/trader_workflow.py`, `src/ops/coaching.py`, `src/interfaces/cli/ops.py`, `src/ops/dashboard.py`, `src/interfaces/cli/report.py`), validation playbook `docs/validation_playbook/AC10_human_performance.yaml`. Tests: `pytest tests/unit/test_trader_workflow_telemetry.py tests/unit/test_coaching_cli.py`. Design cross-check: §65.1-§65.3. | None. |
| M2+ Compliance regression suite | M2+ | Done | TicketScenarioGenerator + ComplianceRegressionRunner + CLI regression commands (`tools/compliance_ticket_generator.py`, `tools/compliance_regression.py`, `src/interfaces/cli/compliance.py`, `src/interfaces/cli/__init__.py`), runbook `docs/runbooks/RUN-COMPLIANCE-02.md`, validation playbooks `docs/validation_playbook/AC31_stop_freeze.yaml`, `docs/validation_playbook/AC41_capital_guard.yaml`, metrics schema `docs/schemas/compliance_regression.schema.json`, reporter/agenda integration (`src/interfaces/cli/report.py`, `src/ops/agenda.py`). Tests: `pytest tests/unit/test_ticket_scenario_generator.py tests/unit/test_compliance_regression_runner.py tests/integration/test_compliance_regression_cli.py`. Re-ran tests: `pytest tests/unit/test_ticket_scenario_generator.py tests/unit/test_compliance_regression_runner.py tests/integration/test_compliance_regression_cli.py`. Design cross-check: §61.1-§61.4 (PreTradeComplianceService未実装のためbroker_rulesベースの簡易評価)。 | None. |
| M2+ BackOffice ledger | M2+ | Done | BackOffice ledger snapshot generation + finance ledger CLI (`src/backoffice/ledger.py`, `src/interfaces/cli/finance.py`, `src/interfaces/cli/__init__.py`), template `reports/tax/ledger_summary_TEMPLATE.md`; review fixes: feature flag profile defaults to mode, non-live skips events without mode, JSONL outputs per period (`ledger_<mode>_<period>.jsonl`), tax template placeholders + fee writeoff scenario. Tests: `pytest tests/unit/test_backoffice_ledger.py tests/unit/test_tax_report_generator.py`. Design cross-check: §47.1. | None. |
| M2+ Research workspace | M2+ | Done | Research workspace checks + notebook runner + artifact registry (`tools/research_workspace.py`, `tools/run_notebook.py`, `src/interfaces/cli/research.py`, `src/research/artifacts.py`); tests: `pytest tests/unit/test_research_workspace_manager.py tests/integration/test_research_notebook_cli.py tests/unit/test_research_artifact_registry.py tests/integration/test_research_data_sync.py`. Design cross-check: §55.1-§55.4. | None. |
| M2+ Real-time feed evaluation | M2+ | Done | RealTimeFeedEvaluator + feed-eval CLI + runbook/template (`src/data/realtime_evaluator.py`, `src/interfaces/cli/feed_eval.py`, `reports/performance/feed_evaluation/templates/eval.md`, `docs/runbooks/RUN-DATA-07.md`), thresholds + alerts, manifest update on promote, validation playbook (`docs/validation_playbook/M12_feed_readiness.yaml`). Tests: `pytest tests/unit/test_real_time_feed_evaluator.py tests/cli/test_tradectl_feed_eval.py tests/integration/test_feed_eval_shadow.py`. Design cross-check: §49.1-§49.3. | None. |
| M2+ Licensing governance | M2+ | Done | LicenseRegistryService + CLI/Runbook/templates (`src/governance/license_registry.py`, `src/interfaces/cli/licensing.py`, `docs/runbooks/GOV-LIC-01.md`, `reports/governance/licensing/templates/review.md`), validation playbook (`docs/validation_playbook/M12_license_compliance.yaml`), feed eval licensing guard (`tests/integration/test_feed_eval_with_license.py`). Tests: `pytest tests/unit/test_license_registry.py tests/integration/test_licensing_cli.py tests/integration/test_feed_eval_with_license.py`. Design cross-check: §50.1-§50.3. | None. |
| M2+ Strategy board & lifecycle | M2+ | Done | StrategyBoardService + CLI + agenda template (`src/governance/strategy_board.py`, `src/interfaces/cli/governance.py`, `reports/governance/strategy_board/templates/agenda.md`) and Lifecycle orchestrator + CLI + runbook/playbook (`src/governance/lifecycle.py`, `docs/runbooks/GOV-LIFECYCLE-01.md`, `docs/validation_playbook/strategy_lifecycle.yaml`). Tests: `pytest tests/unit/test_strategy_board_service.py tests/integration/test_strategy_board_cli.py tests/unit/test_strategy_lifecycle_orchestrator.py tests/integration/test_lifecycle_cli.py`. Design cross-check: §56.1-§57.4. | None. |
| M2+ Multi-account aggregation | M2+ | Done | AccountAggregator enhancements + account CLI aggregate/diff + portfolio state template. PositionRecord serialization fixed + statement_path validation enforced (`src/accounts/aggregator.py`, `src/interfaces/cli/accounts.py`, `src/interfaces/cli/__init__.py`, `reports/performance/portfolio/templates/state.md`, `accounts/demo_broker/demo_account.yaml`). Tests: `pytest tests/unit/test_account_aggregator.py tests/integration/test_accounts_cli.py`. Re-ran tests: `pytest tests/unit/test_account_aggregator.py tests/integration/test_accounts_cli.py`. Design cross-check: §51.1/§51.4. | None. |
| M2+ Portfolio exposure & rebalance | M2+ | Done | PortfolioExposureAnalyzer thresholds + variance detection (`src/risk/portfolio_exposure.py`, `config/portfolio_exposure.yaml`), account CLI variance/coverage/rebalance (`src/interfaces/cli/accounts.py`, `src/interfaces/cli/__init__.py`), runbook/playbook (`docs/runbooks/RUN-ACCOUNT-02.md`, `docs/validation_playbook/M2_account_aggregation.yaml`). Aggregate variance now passes mapping into analyzer (`src/accounts/aggregator.py`). Tests: `pytest tests/unit/test_portfolio_exposure_analyzer.py tests/integration/test_account_rebalance_cli.py tests/unit/test_account_aggregator.py` (re-run ok). Re-ran tests: `pytest tests/unit/test_portfolio_exposure_analyzer.py tests/integration/test_account_rebalance_cli.py tests/unit/test_account_aggregator.py`. Design cross-check: §51.2-§51.5. | None. |
| M1.1+ Governance/Drills/Docs hardening | M1.1+ | Done | OpsDrillService hardening + CLI drill commands + OpsAgenda/Evidence/Automation integration + runbook/validation/critical-first agenda logic (degraded_ack completion) (`src/ops/drills.py`, `src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`, `src/ops/evidence.py`, `src/ops/agenda.py`); tests: `pytest tests/unit/test_ops_drill_service.py tests/unit/test_cli_ops_drills.py tests/unit/test_ops_evidence_store.py tests/unit/test_ops_agenda_drills.py tests/unit/test_ops_agenda_status.py` | None. |
| M1.1+ Ops automation track | M1.1+ | Done | OpsWorklog + AutomationEffect + OpsAgenda CLI/metrics/audit (`src/ops/worklog.py`, `src/ops/automation.py`, `src/ops/agenda.py`, `src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`, `tools/automation_effect_report.py`); tests: `pytest tests/unit/test_ops_worklog_service.py tests/integration/test_ops_cli.py tests/unit/test_automation_effect_tracker.py tests/integration/test_ops_automation_cli.py tests/integration/test_ops_agenda_cli.py` | None. |
| M1.1+ Incident postmortem tooling | M1.1+ | Done | Postmortem metrics now include detect/contain timing + evidence hash in validation (`src/ops/postmortem.py`, `docs/validation_playbook/AC43_postmortem.yaml`, `docs/runbooks/RUN-INC-01.md`); timing uses min/max timeline bounds + clamps non-negative; playbook entries normalized (`entries: []`). Tests: `pytest tests/unit/test_incident_postmortem_service.py tests/unit/test_trade_forensics_analyzer.py tests/integration/test_ops_incident_cli.py`. Validation check: `make check-validation`. | None. |
| M1.1+ Risk consent enforcement | M1.1+ | Done | Enforcer metrics/audit fields align with design; device registry encrypted-at-rest with 600 perms + `cryptography` dependency; CLI warns + exits on device binding failure (`src/compliance/risk_disclosure_enforcer.py`, `src/compliance/device_binding.py`, `src/interfaces/cli/compliance_risk.py`, `src/interfaces/cli/__init__.py`, `docs/validation_playbook/AC44_risk_consent.yaml`, `docs/runbooks/COMPLIANCE-01.md`, `pyproject.toml`); tests: `pytest tests/unit/test_risk_disclosure_enforcer.py tests/unit/test_device_binding_service.py tests/integration/test_risk_consent_flow.py tests/unit/test_compliance_risk_cli.py` | None. |
| M2+ SecureShare evidence sharing | M2+ | Done | SecureShareService end-to-end + profiles + runbook (`src/governance/secure_share.py`, `config/share_profiles/*.yaml`, `docs/runbooks/RUN-GOV-02.md`, `docs/governance/share_register.md`), publisher tool (`tools/publish_evidence_bundle.py`), finance share CLI (`src/interfaces/cli/finance.py`, `src/interfaces/cli/__init__.py`), feature flag `governance.secure_share_cli` (`config/feature_flags.yaml`). Archive preserves repo-relative paths + missing file raises error; manifest path matching uses resolved paths. Tests: `pytest tests/unit/test_secure_share_service.py tests/unit/test_evidence_bundle_publisher.py tests/integration/test_finance_share_cli.py`. Design cross-check: §48.1-§48.4. | None. |
| M2+ Research/Stress/Ideas/Governance | M2+ | In progress | Stress lab (MarginStressLab + CapitalAllocationGuard + CorrelationGuard simulate) + CLI `tradectl risk stress run/compare` + envelope apply/simulate + presets config + metrics/audit/envelopes (`src/risk/stress_lab.py`, `src/risk/capital_guard.py`, `src/risk/correlation_guard.py`, `src/interfaces/cli/risk_stress.py`, `config/risk/margin_stress_presets.yaml`); envelope serialization now uses safe_dump fallback to JSON and report stamp uses UTC for consistency. Tests: `pytest tests/unit/test_margin_stress_lab.py tests/unit/test_stress_simulation.py tests/unit/test_risk_stress_cli.py`; Promotion checklist core + CLI checklist/promote/simulate + metrics/validation/ops evidence integration (`src/research/promotion.py`, `src/research/experiment.py`, `src/interfaces/cli/research_promote.py`, `src/interfaces/cli/__init__.py`, `metrics/promotion_gate.jsonl`, `docs/validation_playbook/AC46_promotion_gate.yaml`, `logs/events/ops.agenda.jsonl`), tests: `pytest tests/unit/test_promotion_checklist.py tests/unit/test_research_promote_cli.py tests/unit/test_promotion_gate_metrics.py`; TradeJournalService now SQLite-backed with weekly summary/metrics (`src/journal/service.py`, `src/journal/repository.py`, tests: `pytest -k trade_journal_service`); Benchmark ingest/validate + replay implemented (`src/benchmark/ingest.py`, `src/benchmark/replay.py`, `src/interfaces/cli/benchmark.py`, tests: `pytest tests/unit/test_benchmark_ingest.py tests/unit/test_benchmark_validate_manual.py tests/unit/test_benchmark_replay.py`); AttributionEngine + 週次レポート統合 (`src/reporter/attribution.py`, `src/interfaces/cli/report.py`, tests: `pytest tests/unit/test_attribution_engine.py tests/integration/test_weekly_report_attribution.py`); Parameter drift monitor + research drift CLI + runbook (`src/research/drift.py`, `src/interfaces/cli/research_drift.py`, `docs/runbooks/RUN-DRIFT-01.md`, tests: `pytest tests/unit/test_parameter_drift_monitor.py tests/integration/test_research_drift_cli.py`); IdeaRegistry/ResearchPipeline + CLI validate (`src/research/registry.py`, `src/research/pipeline.py`, `src/interfaces/cli/research_idea.py`, `src/interfaces/cli/research_pipeline.py`, tests: `pytest tests/unit/test_research_registry.py tests/unit/test_research_pipeline.py tests/integration/test_research_idea_cli.py tests/integration/test_research_validate_cli.py`); IdeaPipelineManager + checklist templates + CLI evidence bundle/report + Ops agenda/readiness linkage (`src/ideas/manager.py`, `docs/templates/idea_checklists/*.yaml`, `src/interfaces/cli/research_idea.py`, `src/ops/agenda.py`, `src/ops_readiness/evaluator.py`, `src/reporter/templates/idea_pipeline_weekly.md`, tests: `pytest tests/unit/test_idea_pipeline_manager.py tests/integration/test_research_idea_cli.py tests/unit/test_ops_agenda_status.py`); Strategy manifest validation/renewal + scoring + board integration with ResearchManifest link/risk band checks (`src/strategies/manifest.py`, `src/strategies/scoring.py`, `src/interfaces/cli/strategy_manifest.py`, `src/interfaces/cli/strategy_scoring.py`, `src/interfaces/cli/board.py`, runbooks `docs/runbooks/RES-MANIFEST-01.md`, `docs/runbooks/RES-SCORE-01.md`, tests: `pytest tests/unit/test_strategy_manifest_validator.py tests/unit/test_strategy_scoring.py tests/integration/test_strategy_manifest_cli.py tests/integration/test_board_scores.py`); Experiment tracker core + scheduler + CLI + playbook/runbook + Ops Agenda integration (`src/research/experiment.py`, `src/research/scheduler.py`, `src/interfaces/cli/research_experiment.py`, `tools/run_experiment.py`, `docs/validation_playbook/FR09_experiment_tracker.yaml`, `docs/runbooks/STRAT-EXP-01.md`, `src/ops/agenda.py`), tests: `pytest tests/unit/test_experiment_tracker.py tests/integration/test_research_experiment_cli.py` (CLI run now completes only on `--complete` or metrics input). Validation check: `make check-validation` failed (missing Make target). | Pick a phase batch and plan. |
| M3+ Backtest regression CI | M3+ | Done | RegressionBacktestSuite core + tool/CLI/CI wiring (`src/backtest/regression.py`, `tools/regression/backtest.py`, `src/interfaces/cli/backtest_regression.py`, `ci/regression-backtest.yml`, `Makefile`), ops agenda drift tasks (`src/ops/agenda.py`), validation playbook `AC13_regression` + runbook update (`docs/validation_playbook/AC13_regression.yaml`, `docs/runbooks/STRAT-M1-VALIDATION.md`). Review fix: error if no scenarios configured, clamp config concurrency/runtime to >=1, CLI/tool surface config error. Tests: `pytest tests/regression/test_regression_backtest_suite.py tests/regression/test_regression_backtest_cli.py`; `python3 tools/check_validation_playbook.py --category regression`. Tests not rerun for this change. | None. |
| M3+ Governance & Compliance | M3+ | In progress | Risk consent is implemented (`src/compliance/*`, `src/interfaces/cli/compliance_risk.py`); model risk register/CLI/artifact manifest + weekly summary integration added (`src/governance/model_risk.py`, `src/interfaces/cli/model_risk.py`, `tools/generate_explainability.py`, `src/interfaces/cli/report.py`, `src/reporter/templates/weekly_m1_core*.md`); access governance (principals/devices/reviews/enforce/report) + ops agenda tasks + validation/runbook now implemented (`src/security/access.py`, `src/interfaces/cli/access.py`, `src/interfaces/cli/__init__.py`, `src/ops/agenda.py`, `docs/validation_playbook/AC44_access.yaml`, `docs/runbooks/SEC-ACCESS-01.md`) | Pick a phase batch and plan. |
| M3+ Degradation & Sunset workflows | M3+ | Done | Degradation playbook orchestrator + CLI + validation/runbook + report summary (`src/ops/degradation.py`, `src/interfaces/cli/degradation.py`, `src/interfaces/cli/__init__.py`, `docs/validation_playbook/AC34_degradation.yaml`, `docs/runbooks/RUN-DEGRADE-01.md`, `docs/schemas/degradation_playbook.schema.json`, `reports/weekly/templates/m1_plus.md`); Sunset workflow service + CLI + reallocation suggestions + runbook/playbook updates (`src/governance/sunset.py`, `src/interfaces/cli/governance_sunset.py`, `src/interfaces/cli/portfolio.py`, `src/portfolio/reallocation.py`, `docs/validation_playbook/AC55_sunset.yaml`, `docs/runbooks/STRAT-SUNSET-01.md`, `docs/validation_playbook/index.md`). Review fixes: guard unknown degradation scenario, enforce evidence existence, normalize playbook payloads to dict, ensure playbook category defaults; added missing-evidence test. Tests: `pytest tests/unit/test_degradation_playbook.py tests/integration/test_degradation_cli.py tests/unit/test_strategy_sunset_service.py tests/unit/test_portfolio_reallocator.py tests/integration/test_governance_sunset_cli.py tests/integration/test_portfolio_reallocation_cli.py`. Validation: `make check-validation`. Design cross-check: §66.3/§69.4. | None. |
| M3+ DocOps registry & decision/onboarding | M3+ | Done | DocsRegistry + RunbookInventoryService + DocLint/check-runbooks + CLI `docs runbook *` (`src/docops/registry.py`, `src/docops/runbook_inventory.py`, `tools/doclint.py`, `tools/check_runbooks.py`, `src/interfaces/cli/docops.py`, `src/interfaces/cli/__init__.py`, `Makefile`). Decision journal + onboarding services + CLI (`src/docops/journal.py`, `src/docops/onboarding.py`, `src/interfaces/cli/decision.py`, `src/interfaces/cli/onboarding.py`, `docs/onboarding.md`, `docs/validation_playbook/AC16_onboarding.yaml`). DocOps export bundle to SecureShare (`src/docops/exporter.py`, `src/interfaces/cli/docops_export.py`, `src/interfaces/cli/__init__.py`). DocBuild pipeline + docs CLI build/diff/lint/serve (`tools/docbuild.py`, `src/interfaces/cli/docs_build.py`, `src/interfaces/cli/__init__.py`) and DocLint UX checks (`tools/doclint.py`). Tests: `pytest tests/unit/test_docs_registry.py tests/unit/test_runbook_inventory.py tests/integration/test_docops_cli.py tests/unit/test_decision_journal.py tests/unit/test_onboarding_service.py tests/integration/test_onboarding_cli.py tests/integration/test_docops_export_cli.py tests/unit/test_docbuild.py tests/unit/test_doclint.py`. Design cross-check: §58.1-§59.1. | None. |

## Release Checklist
When preparing a release, follow `docs/release_checklist.md`. This is separate from the day-to-day task tracking above.

## Implementation Review Checklist
Use this checklist after completing a task or batch.

- [x] Evidence artifacts captured (logs/reports paths noted).
- [x] Tests executed and recorded in Notes.
- [x] CLI output verified for user-facing flows.
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
| `EP04-P1` | 34.1 TradeJournalService | detailed_design_fx_signal_tool_v1.md:6029 | done | TradeJournalServiceをSQLite実装へ移行し、週次サマリ/メトリクス/監査ログを追加（`src/journal/service.py`, `src/journal/repository.py`）。CLI/レポートのDBパスへ更新済（`src/interfaces/cli/__init__.py`, `src/interfaces/cli/report.py`）。`entry_id`/note連携の競合修正 + UUIDv7採用 + 日次監査ログパス計算を追加。UUIDv7のvariantビット修正も反映。Tests: `pytest -k trade_journal_service`. Design cross-check: §34.1/§3.14. Feature flag配線はEP04-P2で対応。 |
| `EP04-P2` | 34.2 CLI/UX統合 | detailed_design_fx_signal_tool_v1.md:6062 | done | Journal CLIに add-note/review/stats + フィルタ付きlistを追加し、journalフラグで週次レポート連携をゲート化（`src/interfaces/cli/journal.py`, `src/interfaces/cli/__init__.py`, `src/interfaces/cli/report.py`, `config/feature_flags.yaml`）。Tests: `pytest tests/cli/test_tradectl_journal_cli.py tests/cli/test_tradectl_report_weekly.py`. Design cross-check: §34.2/§34.3. |
| `EP04-P3` | 34.3 Runbook・Reporter連携 | detailed_design_fx_signal_tool_v1.md:6079 | done | Runbook `RUN-JOURNAL-01` 新設、Validation Playbook `AC37_journal` 追加、index更新、runbook changelog更新（`docs/runbooks/RUN-JOURNAL-01.md`, `docs/validation_playbook/AC37_journal.yaml`, `docs/validation_playbook/index.md`, `reports/governance/runbook_changelog.md`）。Design cross-check: §34.3. |
| `EP03-P6` | 24.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5648 | done | LiquidityMonitorService + metrics/logging + GateState連携を実装（`src/risk/liquidity_monitor.py`, `metrics/liquidity_monitor.jsonl`, `snapshots/latest/liquidity_state.json`）。テスト: `pytest tests/unit/test_liquidity_monitor.py`. |
| `EP03-P7` | 24.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5649 | done | CLI `tradectl liquidity *` + Boardバナー + Ticket WARN統合 + Ops dashboard CLIを実装（`src/interfaces/cli/liquidity.py`, `src/interfaces/cli/board.py`, `src/ticket/builder.py`, `src/interfaces/cli/ops_dashboard.py`）。流動性取込は`--window`指定対応、Ops dashboardは欠損3回連続で警告。テスト: `pytest tests/unit/test_cli_liquidity.py tests/unit/test_ticket_builder.py tests/unit/test_ops_dashboard.py`. |
| `EP03-P8` | 24.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5650 | done | Emergency playbook stub + ops_worklog自動記録を追加（`src/ops/emergency.py`, `src/interfaces/cli/__init__.py`, `src/risk/liquidity_monitor.py`）。CLI: `tradectl emergency trigger --simulate --scenario liquidity_divergence`. |
| `EP05-P3` | 25.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5707 | done | Statementパーサ/設定テンプレ/単体テストを追加済（`src/reconciliation/statements.py`）。 Other refs: 36.3 テスト & Codex Packet (detailed_design_fx_signal_tool_v1.md:6203, status done) |
| `EP05-P4` | 25.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5708 | done | `tradectl reconcile statements/preview/scaffold`とCLI統合テストを追加済。 |
| `EP05-P5` | 25.4 テスト & Codex Packet計画 | detailed_design_fx_signal_tool_v1.md:5709 | done | Validation Playbook同期（スタブ）を追加済。 |
| `EP06-P1` | 26.4 Codex Packet計画 & テレメトリ | detailed_design_fx_signal_tool_v1.md:5772 | done | IdeaRegistry + CLI `idea list/stage/checklist` を実装（`src/research/registry.py`, `src/interfaces/cli/research_idea.py`, `docs/runbooks/RES-IDEA-01.md`）。Tests: `pytest tests/unit/test_research_registry.py tests/integration/test_research_idea_cli.py`. Design cross-check: §26.1/§26.3. |
| `EP06-P2` | 26.4 Codex Packet計画 & テレメトリ | detailed_design_fx_signal_tool_v1.md:5773 | done | ResearchPipeline Validation + CLI `tradectl research validate`/`tradectl research manifest` とValidation Suite設定を追加（`src/research/pipeline.py`, `src/interfaces/cli/research_pipeline.py`, `config/research_validation.yaml`）。Tests: `pytest tests/unit/test_research_pipeline.py tests/integration/test_research_validate_cli.py tests/integration/test_research_manifest_cli.py`. Design cross-check: §26.2. |
| `EP35-DRIFT-P1` | 35.3 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6151 | done | ParameterDriftMonitor を実装（`src/research/drift.py`）、drift_monitor設定/スキーマ拡張（`config/drift_monitor.yaml`, `docs/schemas/drift_monitor.schema.json`）。欠損時は`research.drift.cleared`を発火しないよう調整。Tests: `pytest tests/unit/test_parameter_drift_monitor.py`. Design cross-check: §35.1/§35.3. |
| `EP35-DRIFT-P2` | 35.3 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6152 | done | `tradectl research drift scan` を追加し、feature flag/Health連携/Runbookを整備（`src/interfaces/cli/research_drift.py`, `src/interfaces/cli/__init__.py`, `config/feature_flags.yaml`, `docs/runbooks/RUN-DRIFT-01.md`, `reports/governance/runbook_changelog.md`）。RunbookはAC-47に割当。Tests: `pytest tests/integration/test_research_drift_cli.py`. Design cross-check: §35.2/§35.3. |
| `EP06-P3` | 26.4 Codex Packet計画 & テレメトリ | detailed_design_fx_signal_tool_v1.md:5774 | done | 昇格処理 + audit/event記録 + CLI `tradectl research promote` を追加（`src/research/promotion.py`, `src/interfaces/cli/research_promote.py`, `src/interfaces/cli/__init__.py`）。Validation playbook `AC46_promotion_gate` を追加（`docs/validation_playbook/AC46_promotion_gate.yaml`）。Tests: `pytest tests/unit/test_research_promotion.py tests/integration/test_research_promote_cli.py`. Design cross-check: §26.2/§26.3. |
| `EP05-P1` | 36.3 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6201 | done | Benchmark ingest/validateを実装（`src/benchmark/ingest.py`, `src/interfaces/cli/benchmark.py`）。Manual validationはpair matchingで一致検証し、signoffとparquet出力を生成。出力パスは `YYYYMMDD_<symbol>_<timeframe>_<mode>.parquet` で衝突回避。Tests: `pytest tests/unit/test_benchmark_ingest.py tests/unit/test_benchmark_validate_manual.py`. Design cross-check: §3.18.1/§36.1. |
| `EP05-P2` | 36.3 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6202 | done | BenchmarkReplayService と CLI compare を実装（`src/benchmark/replay.py`, `src/interfaces/cli/benchmark.py`）。比較結果を `benchmark_runs/<mode>/<YYYYMMDD>_<window>.parquet` に保存し、Markdown (`--export`) と JSON (`--export-json`) を分離。raw配下のproviderディレクトリも探索するよう改善。Tests: `pytest -k benchmark_replay`. Design cross-check: §36.1/§36.2. |
| `EP05-P3` | 36.3 テスト & Codex Packet | detailed_design_fx_signal_tool_v1.md:6203 | done | 週次レポートへ Benchmark Comparison セクションを追加し、feature flag (`benchmark.replay`) でゲート化。Runbook `RES-BENCHMARK-01` 追加（`src/interfaces/cli/report.py`, `src/reporter/templates/weekly_m1_core*.md`, `config/feature_flags.yaml`, `docs/runbooks/RES-BENCHMARK-01.md`）。providerヒントをレポートに表示。Tests: `pytest -k benchmark_replay`, `pytest -k benchmark_summary`. Design cross-check: §36.2/§36.3. |
| `EP06-MR-P1` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6747 | done | ModelRiskRegisterService + Markdownローダー/データモデルを実装（`src/governance/model_risk.py`, `docs/governance/model_risk_register.md`）。Tests: `pytest tests/unit/test_model_risk_register.py`. Design cross-check: §46.1. |
| `EP06-MR-P2` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6748 | done | Explainability artifact manifest登録/整備 + stub generatorを実装（`src/governance/model_risk.py`, `tools/generate_explainability.py`）。Tests: `pytest tests/unit/test_model_risk_artifacts.py tests/unit/test_model_risk_cli.py`. Design cross-check: §46.2. |
| `EP06-MR-P3` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6749 | done | Model risk CLI（status/review/artifact-add/escalate）+ audit/metrics + feature flagを実装（`src/interfaces/cli/model_risk.py`, `src/interfaces/cli/__init__.py`, `config/feature_flags.yaml`）。Tests: `pytest tests/unit/test_model_risk_cli.py`. Design cross-check: §46.3. |
| `EP06-MR-P4` | 46.5 Codex Packet計画（Model Risk Track） | detailed_design_fx_signal_tool_v1.md:6750 | done | 週次レポートへModel Risk Summaryを追加（`src/interfaces/cli/report.py`, `src/reporter/templates/weekly_m1_core*.md`）。Tests: `pytest tests/unit/test_cli_report.py`. Design cross-check: §46.4. |
| `EP07-BO-P1` | 47.5 Codex Packet計画（BackOffice/Tax Track） | detailed_design_fx_signal_tool_v1.md:6841 | done | BackOffice ledger snapshot生成 + finance ledger CLI を追加（`src/backoffice/ledger.py`, `src/interfaces/cli/finance.py`, `src/interfaces/cli/__init__.py`）。テンプレート `reports/tax/ledger_summary_TEMPLATE.md` を追加。Feature flag `finance.backoffice_enabled` を追加（`config/feature_flags.yaml`）。Review fixes: feature flag profile defaults to mode, non-live skips events without mode, JSONL outputs per period (`ledger_<mode>_<period>.jsonl`). Tests: `pytest tests/unit/test_backoffice_ledger.py`. Design cross-check: §47.1. |
| `EP07-BO-P2` | 47.5 Codex Packet計画（BackOffice/Tax Track） | detailed_design_fx_signal_tool_v1.md:6842 | done | TaxReportGenerator/CLI/CSV/監査イベントを追加（`src/backoffice/tax_report.py`, `tools/generate_tax_report.py`, `src/interfaces/cli/finance.py`, `src/interfaces/cli/__init__.py`）。TaxLot出力（`jsonl/backoffice/taxlots_<period>.jsonl`）と帳票テンプレ更新（`reports/tax/ledger_summary_TEMPLATE.md`, `docs/templates/tax_report_jp.md`）。Config: `config/tax/jp.yaml`. Review fixes: テンプレート差し込みと`with_fee_writeoff`反映。Tests: `pytest tests/unit/test_tax_report_generator.py tests/integration/test_finance_cli.py tests/unit/test_backoffice_ledger.py`. Design cross-check: §47.2/§47.4. |
| `EP07-BO-P3` | 47.5 Codex Packet計画（BackOffice/Tax Track） | detailed_design_fx_signal_tool_v1.md:6843 | done | Audit bundle finance添付/manifest hash/CLI `--with-finance` を追加（`src/audit/bundle.py`, `src/interfaces/cli/__init__.py`）。Runbook `RUN-TAX-01` を自動添付に更新（v1.2）。メトリクスに `generation_duration_ms` を追加。Review fix: DataManifest重複登録を抑制。Tests: `pytest tests/integration/test_audit_bundle_cli.py`. Design cross-check: §47.3-§47.4. |
| `EP08-SS-P1` | 48.5 Codex Packet計画（Secure Sharing Track） | detailed_design_fx_signal_tool_v1.md:6914 | done | SecureShareService core (profile load, scope/manifest checks, manifest/signature, audit/metrics/register, publish/revoke) を実装（`src/governance/secure_share.py`）。Archiveはrepo相対パスで保持し、暗号化時に欠損ファイルがあればエラー化。Share profiles + register templateを追加（`config/share_profiles/*.yaml`, `docs/governance/share_register.md`）。Tests: `pytest tests/unit/test_secure_share_service.py`. Design cross-check: §48.1/§48.2. |
| `EP08-SS-P2` | 48.5 Codex Packet計画（Secure Sharing Track） | detailed_design_fx_signal_tool_v1.md:6915 | done | Evidence bundle publisher tool + research idea CLI更新 + feature flag/finance share CLI を実装（`tools/publish_evidence_bundle.py`, `src/interfaces/cli/research_idea.py`, `src/interfaces/cli/finance.py`, `src/interfaces/cli/__init__.py`, `config/feature_flags.yaml`）。Tests: `pytest tests/unit/test_evidence_bundle_publisher.py tests/integration/test_finance_share_cli.py`. Design cross-check: §48.2/§48.3. |
| `EP08-SS-P3` | 48.5 Codex Packet計画（Secure Sharing Track） | detailed_design_fx_signal_tool_v1.md:6916 | done | Runbook `RUN-GOV-02` を追加し、share profileテンプレ/運用導線を整理（`docs/runbooks/RUN-GOV-02.md`, `config/share_profiles/TEMPLATE.yaml`）。Publish時のaudit/metrics/register更新を実装済み。Tests: `pytest tests/unit/test_secure_share_service.py tests/unit/test_evidence_bundle_publisher.py`. Design cross-check: §48.3/§48.4. |
| `EP09-RTF-P1` | 49.4 Codex Packet計画（Real-time Feed Track） | detailed_design_fx_signal_tool_v1.md:6972 | done | RealTimeFeedEvaluator + ProviderCapabilityRegistry + metrics template (`src/data/realtime_evaluator.py`, `config/providers/real_time_candidates.yaml`, `metrics/feed_evaluation_TEMPL.jsonl`). Tests: `pytest tests/unit/test_real_time_feed_evaluator.py`. Design cross-check: §49.1. |
| `EP09-RTF-P2` | 49.4 Codex Packet計画（Real-time Feed Track） | detailed_design_fx_signal_tool_v1.md:6973 | done | CLI `tradectl data feed-eval` + report template + Runbook `RUN-DATA-07` (`src/interfaces/cli/feed_eval.py`, `reports/performance/feed_evaluation/templates/eval.md`, `docs/runbooks/RUN-DATA-07.md`). Tests: `pytest tests/cli/test_tradectl_feed_eval.py`. Design cross-check: §49.2/§49.3. |
| `EP09-RTF-P3` | 49.4 Codex Packet計画（Real-time Feed Track） | detailed_design_fx_signal_tool_v1.md:6974 | done | Threshold proposal + alert hook + DataManifest update on promote + Validation playbook `M12_feed_readiness` (`src/data/realtime_evaluator.py`, `src/interfaces/cli/feed_eval.py`, `docs/validation_playbook/M12_feed_readiness.yaml`). Tests: `pytest tests/integration/test_feed_eval_shadow.py`. Design cross-check: §49.3. |
| `EP09-LIC-P1` | 50.3 テスト & Codex Packet計画（Licensing Track） | detailed_design_fx_signal_tool_v1.md:7028 | done | LicenseRegistryService + registry scaffold + metrics (`src/governance/license_registry.py`, `reports/governance/licensing/license_registry.yaml`, `metrics/licensing.jsonl`). Tests: `pytest tests/unit/test_license_registry.py`. Design cross-check: §50.1. |
| `EP09-LIC-P2` | 50.3 テスト & Codex Packet計画（Licensing Track） | detailed_design_fx_signal_tool_v1.md:7029 | done | CLI/Runbook/テンプレ整備（`src/interfaces/cli/licensing.py`, `docs/runbooks/GOV-LIC-01.md`, `reports/governance/licensing/templates/review.md`）。Tests: `pytest tests/integration/test_licensing_cli.py`. Design cross-check: §50.2. |
| `EP09-LIC-P3` | 50.3 テスト & Codex Packet計画（Licensing Track） | detailed_design_fx_signal_tool_v1.md:7030 | done | Feed eval licensing guard + validation playbook `M12_license_compliance` (`src/data/realtime_evaluator.py`, `docs/validation_playbook/M12_license_compliance.yaml`). Tests: `pytest tests/integration/test_feed_eval_with_license.py`. Design cross-check: §50.3. |
| `EP10-ACC-P1` | 51.6 Codex Packet計画（Multi-Account Track） | detailed_design_fx_signal_tool_v1.md:7132 | done | AccountProfile読み込み（accounts/配下も対応）、aggregate/persist/diff、`account` CLI初期実装、portfolio stateテンプレ追加。PositionRecordのto_dict対応とstatement_path必須化を追加（`src/accounts/aggregator.py`, `src/interfaces/cli/accounts.py`, `reports/performance/portfolio/templates/state.md`, `accounts/demo_broker/demo_account.yaml`）。Tests: `pytest tests/unit/test_account_aggregator.py tests/integration/test_accounts_cli.py`. Re-ran tests: `pytest tests/unit/test_account_aggregator.py tests/integration/test_accounts_cli.py`. Design cross-check: §51.1/§51.4. |
| `EP10-ACC-P2` | 51.6 Codex Packet計画（Multi-Account Track） | detailed_design_fx_signal_tool_v1.md:7133 | done | PortfolioExposureAnalyzer + thresholds + variance検出（`src/risk/portfolio_exposure.py`, `config/portfolio_exposure.yaml`）。Aggregate時のvariance検出はstate dictを渡すよう修正（`src/accounts/aggregator.py`）。Tests: `pytest tests/unit/test_portfolio_exposure_analyzer.py tests/unit/test_account_aggregator.py` (re-run ok). Re-ran tests: `pytest tests/unit/test_portfolio_exposure_analyzer.py tests/unit/test_account_aggregator.py`. Design cross-check: §51.2/§51.5. |
| `EP10-ACC-P3` | 51.6 Codex Packet計画（Multi-Account Track） | detailed_design_fx_signal_tool_v1.md:7134 | done | Runbook/Validation Playbook整備 + account CLI rebalance/coverage (`docs/runbooks/RUN-ACCOUNT-02.md`, `docs/validation_playbook/M2_account_aggregation.yaml`, `src/interfaces/cli/accounts.py`). Tests: `pytest tests/integration/test_account_rebalance_cli.py`. Re-ran tests: `pytest tests/integration/test_account_rebalance_cli.py`. Design cross-check: §51.3/§51.4/§51.5. |
| `EP11-OPS-P1` | 52.6 Codex Packet計画（Ops Automation Track） | detailed_design_fx_signal_tool_v1.md:7259 | done | OpsWorklogService query timezone fix + CLI `ops log add/list` (`src/ops/worklog.py`, `src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`); tests: `pytest tests/unit/test_ops_worklog_service.py tests/integration/test_ops_cli.py`. |
| `EP11-OPS-P2` | 52.6 Codex Packet計画（Ops Automation Track） | detailed_design_fx_signal_tool_v1.md:7260 | done | AutomationEffectTracker metrics/audit hooks + CLI `ops automation add` + report tool (`src/ops/automation.py`, `src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`, `tools/automation_effect_report.py`, `Makefile`); tests: `pytest tests/unit/test_automation_effect_tracker.py tests/integration/test_ops_automation_cli.py`. |
| `EP11-OPS-P3` | 52.6 Codex Packet計画（Ops Automation Track） | detailed_design_fx_signal_tool_v1.md:7261 | done | OpsAgenda CLI + metrics/audit logs + critical-first/runbook/validation pending logic + degraded_ack completion (`src/ops/agenda.py`, `src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`); tests: `pytest tests/integration/test_ops_agenda_cli.py tests/unit/test_ops_agenda_drills.py tests/unit/test_ops_agenda_status.py`. |
| `EP11-DRILL-P1` | 53.4 テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7342 | done | OpsDrillServiceのrunbook参照検証/レポート生成/metrics/events追加（`src/ops/drills.py`, `docs/templates/drill_report.md`）とユニットテスト追加（`pytest tests/unit/test_ops_drill_service.py`）。 |
| `EP11-DRILL-P2` | 53.4 テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7343 | done | Drill CLI helpers + Typer wiring (`src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`); tests: `pytest tests/unit/test_cli_ops_drills.py`. |
| `EP11-DRILL-P3` | 53.4 テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7344 | done | OpsAgenda drill pending/defer filtering + OpsEvidenceStore/AutomationEffect hooks (`src/ops/agenda.py`, `src/ops/evidence.py`, `src/ops/drills.py`); tests: `pytest tests/unit/test_ops_agenda_drills.py tests/unit/test_ops_evidence_store.py`. |
| `EP06-IDEA-P1` | 54.5 テスト戦略とCodex Packet | detailed_design_fx_signal_tool_v1.md:7436 | done | IdeaPipelineManagerコア実装（stage定義/チェックリスト/遷移/監査/メトリクス）と設定/テンプレ追加（`src/ideas/manager.py`, `config/idea_pipeline.yaml`, `docs/templates/idea_checklists/*.yaml`, `schema/idea_pipeline.schema.json`）。遷移判定はtarget stageの要件を評価し、`index.yaml`の`current_stage`も更新。Tests: `pytest tests/unit/test_idea_pipeline_manager.py`. Design cross-check: §54.1/§54.2. |
| `EP06-IDEA-P2` | 54.5 テスト戦略とCodex Packet | detailed_design_fx_signal_tool_v1.md:7437 | done | CLI統合（idea show/stage/checklist-update/evidence-bundle/report）とレポートテンプレ追加（`src/interfaces/cli/research_idea.py`, `src/interfaces/cli/__init__.py`, `src/reporter/templates/idea_pipeline_weekly.md`）。Idea PipelineはFeature Flagでガード。Tests: `pytest tests/integration/test_research_idea_cli.py`. Design cross-check: §54.3/§54.4. |
| `EP06-IDEA-P3` | 54.5 テスト戦略とCodex Packet | detailed_design_fx_signal_tool_v1.md:7438 | done | Ops AgendaにIdea Pipelineの停滞/未完了タスクを反映し、Ops Readinessでidea_pipelineメトリクスを評価、SecureShare証跡バンドルを最小実装（`src/ops/agenda.py`, `src/ops_readiness/evaluator.py`, `src/ops_readiness/evaluator_stub.py`, `src/governance/secure_share.py`, `docs/runbooks/GOV-IDEA-01.md`）。Feature Flag無効時はidea_pipeline評価をスキップ。Tests: `pytest tests/unit/test_ops_agenda_status.py tests/unit/test_ops_readiness_evaluator.py`. Design cross-check: §54.4. |
| `EP07-RSCH-P1` | 55.5 Codex Packet計画（Research Workspace Track） | detailed_design_fx_signal_tool_v1.md:7519 | done | ResearchWorkspaceManager を追加し、環境/パス整合チェックと同期を実装（`tools/research_workspace.py`, `config/research_workspace.yaml`, `requirements-research.lock`）。Tests: `pytest tests/unit/test_research_workspace_manager.py`. Design cross-check: §55.1. |
| `EP07-RSCH-P2` | 55.5 Codex Packet計画（Research Workspace Track） | detailed_design_fx_signal_tool_v1.md:7520 | done | NotebookRunner + CLI `tradectl research notebook run` を追加し、実行レポート生成を実装（`tools/run_notebook.py`, `src/interfaces/cli/research.py`, `src/interfaces/cli/__init__.py`）。Review fix: jupyter未導入時に`execute`をerror化。Tests: `pytest tests/integration/test_research_notebook_cli.py`. Design cross-check: §55.2/§55.4. |
| `EP07-RSCH-P3` | 55.5 Codex Packet計画（Research Workspace Track） | detailed_design_fx_signal_tool_v1.md:7521 | done | ResearchArtifactRegistry + DataManifest連携 + CLI `tradectl research artifact add/list` を実装（`src/research/artifacts.py`, `src/interfaces/cli/research.py`, `src/data/manifest.py`）。Tests: `pytest tests/unit/test_research_artifact_registry.py tests/integration/test_research_data_sync.py`. Design cross-check: §55.3/§55.4. |
| `EP09-BRD-P1` | 56.5 Codex Packet計画（Strategy Board Track） | detailed_design_fx_signal_tool_v1.md:7587 | done | StrategyBoardService基盤 + agendaテンプレ、decision logがoutput_dir配下に保存されるよう整理（`src/governance/strategy_board.py`, `reports/governance/strategy_board/templates/agenda.md`). Tests: `pytest tests/unit/test_strategy_board_service.py`. Design cross-check: §56.1/§56.4. |
| `EP09-BRD-P2` | 56.5 Codex Packet計画（Strategy Board Track） | detailed_design_fx_signal_tool_v1.md:7588 | done | CLI `tradectl governance board *` 追加 (`src/interfaces/cli/governance.py`, `src/interfaces/cli/__init__.py`). Tests: `pytest tests/integration/test_strategy_board_cli.py`. Design cross-check: §56.2. |
| `EP09-BRD-P3` | 56.5 Codex Packet計画（Strategy Board Track） | detailed_design_fx_signal_tool_v1.md:7589 | done | Scoreboard watchlist統合 + Ops/Idea stall反映の最小実装 (`src/strategies/scoreboard.py`, `src/interfaces/cli/governance.py`). Design cross-check: §56.3/§56.4. |
| `EP09-LIFE-P1` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:7672 | done | LifecycleState/GateDefinition + Gate評価基盤 (`src/governance/lifecycle.py`). Tests: `pytest tests/unit/test_strategy_lifecycle_orchestrator.py`. Design cross-check: §57.1. |
| `EP09-LIFE-P2` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:7673 | done | CLI `tradectl governance lifecycle *` + metrics/audit (`src/interfaces/cli/governance.py`, `metrics/strategy_lifecycle.jsonl`) + Runbook `GOV-LIFECYCLE-01`。Tests: `pytest tests/integration/test_lifecycle_cli.py`. Design cross-check: §57.2/§57.3. |
| `EP09-LIFE-P3` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:7674 | done | Validation playbook統合 (`docs/validation_playbook/strategy_lifecycle.yaml`) + lifecycle history export. Design cross-check: §57.3/§57.4. |
| `EP12-DOC-P1` | 58.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7746 | done | DocsRegistry/RunbookInventory + DocLint/check-runbooks + CLI `docs runbook *` を実装（`src/docops/registry.py`, `src/docops/runbook_inventory.py`, `tools/doclint.py`, `tools/check_runbooks.py`, `src/interfaces/cli/docops.py`, `src/interfaces/cli/__init__.py`, `Makefile`）。`runbook status` no-writeはレビューイベントを抑制（`src/docops/runbook_inventory.py`）。Tests: `pytest tests/unit/test_docs_registry.py tests/unit/test_runbook_inventory.py tests/integration/test_docops_cli.py`。Design cross-check: §58.1/§58.2. |
| `EP12-DOC-P2` | 58.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7747 | done | DecisionJournalManager + OnboardingChecklistService + CLI `docs decision *`/`onboarding *` を実装（`src/docops/journal.py`, `src/docops/onboarding.py`, `src/interfaces/cli/decision.py`, `src/interfaces/cli/onboarding.py`, `docs/onboarding.md`, `docs/validation_playbook/AC16_onboarding.yaml`, `src/interfaces/cli/__init__.py`）。Onboarding完了時にAC16 playbookへ追記、dry-run時はレポート生成を回避（`src/docops/onboarding.py`）。Ops agendaイベントとvalidation追記を最小実装で連携。Tests: `pytest tests/unit/test_decision_journal.py tests/unit/test_onboarding_service.py tests/integration/test_onboarding_cli.py`. Design cross-check: §58.3/§58.4. |
| `EP12-DOC-P3` | 58.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7748 | done | DocOps exporter + CLI `docs export` を実装（`src/docops/exporter.py`, `src/interfaces/cli/docops_export.py`, `src/interfaces/cli/__init__.py`）。SecureShareへガバナンス束をエクスポート可能。Tests: `pytest tests/integration/test_docops_export_cli.py`. Design cross-check: §58.4. |
| `EP12-DOC-P4` | 59.3 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7790 | done | DocBuildPipeline + CLI `docs build/diff` を実装（`tools/docbuild.py`, `src/interfaces/cli/docs_build.py`, `src/interfaces/cli/__init__.py`, `Makefile`）。Tests: `pytest tests/unit/test_docbuild.py`. Design cross-check: §59.1/§59.2. |
| `EP12-DOC-P5` | 59.3 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:7791 | done | DocLintのUXカラー検証 + CLI `docs lint` (`tools/doclint.py`, `src/interfaces/cli/docs_build.py`, `src/interfaces/cli/__init__.py`)。Tests: `pytest tests/unit/test_doclint.py`. Design cross-check: §59.1. |
| `EP13-SHADOW-P1` | 60.3 テレメトリ・テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7869 | done | ShadowStateStore + ShadowSessionOrchestratorの基盤を追加（`src/shadow/store.py`, `src/shadow/session.py`, `src/shadow/__init__.py`）。EventログはJSONLで記録し、イベントIDはマイクロ秒精度へ更新。Tests: `pytest tests/unit/test_shadow_state_store.py tests/unit/test_shadow_session_orchestrator.py`. Design cross-check: §60.2. |
| `EP13-SHADOW-P2` | 60.3 テレメトリ・テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7870 | done | SlackShadowBridge + shadow CLI test/replay/status/serveを実装し、replayは出力ログを`shadow_replay.jsonl`へ分離（`src/interfaces/shadow/slack_bridge.py`, `src/interfaces/cli/shadow.py`, `src/interfaces/cli/__init__.py`, `config/feature_flags.yaml`）。Tests: `pytest tests/unit/test_slack_shadow_bridge.py`. Design cross-check: §60.1/§60.2. |
| `EP13-SHADOW-P3` | 60.3 テレメトリ・テスト・Codex Packet | detailed_design_fx_signal_tool_v1.md:7871 | done | GUI Shadow APIのスナップショット/ACK/イベント読み出しを追加し、Runbook整備（`src/interfaces/gui/shadow_api.py`, `docs/runbooks/RUN-SHADOW-01.md`, `docs/runbooks/RUN-SHADOW-02.md`, `docs/schema/shadow_gui.yaml`）。Tests: `pytest tests/unit/test_shadow_gui_api.py`. Design cross-check: §60.2/§60.3. |
| `EP10-COMP-P1` | 61.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:7960 | done | TicketScenarioGeneratorを実装し、broker_rulesとmarket_scenariosからJSONLを生成（`tools/compliance_ticket_generator.py`, `data/market_scenarios/*.json`）。Tests: `pytest tests/unit/test_ticket_scenario_generator.py`. Re-ran tests: `pytest tests/unit/test_ticket_scenario_generator.py`. Design cross-check: §61.1. |
| `EP10-COMP-P2` | 61.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:7961 | done | ComplianceRegressionRunner + CLI `compliance regression generate/run/diff` を追加（`tools/compliance_regression.py`, `src/interfaces/cli/compliance.py`, `src/interfaces/cli/__init__.py`）。Tests: `pytest tests/unit/test_compliance_regression_runner.py tests/integration/test_compliance_regression_cli.py`. Re-ran tests: `pytest tests/unit/test_compliance_regression_runner.py tests/integration/test_compliance_regression_cli.py`. Design cross-check: §61.2（PreTradeComplianceService未実装のためbroker_rulesベースの簡易評価）。 |
| `EP10-COMP-P3` | 61.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:7962 | done | Metrics/Runbook/Validation/Reporter/Ops Agenda連携を追加（`metrics/compliance_regression.json`, `docs/runbooks/RUN-COMPLIANCE-02.md`, `docs/validation_playbook/AC31_stop_freeze.yaml`, `docs/validation_playbook/AC41_capital_guard.yaml`, `docs/schemas/compliance_regression.schema.json`, `src/interfaces/cli/report.py`, `src/ops/agenda.py`）。Tests: `pytest tests/integration/test_compliance_regression_cli.py`. Re-ran tests: `pytest tests/integration/test_compliance_regression_cli.py`. Design cross-check: §61.3/§61.4. |
| `EP08-EXP-P1` | 62.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:8032 | done | ExperimentTrackerServiceコア（Manifest/Run/Promotion/metrics/event）を追加し、ops agenda向けイベントを記録（`src/research/experiment.py`, `src/ops/agenda.py`）。Tests: `pytest tests/unit/test_experiment_tracker.py`. Design cross-check: §62.1. |
| `EP08-EXP-P2` | 62.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:8033 | done | ParameterSweepScheduler + CLI `tradectl research experiment *` を追加（`src/research/scheduler.py`, `src/interfaces/cli/research_experiment.py`, `src/interfaces/cli/__init__.py`, `tools/run_experiment.py`）。CLI runは`--complete`またはmetrics指定時のみ完了処理。Tests: `pytest tests/integration/test_research_experiment_cli.py`. Design cross-check: §62.2. |
| `EP08-EXP-P3` | 62.4 テスト戦略・Codex Packet | detailed_design_fx_signal_tool_v1.md:8034 | done | Validation Playbook `FR09_experiment_tracker` と Runbook `STRAT-EXP-01` を追加し、Validation index と runbook changelog を更新（`docs/validation_playbook/FR09_experiment_tracker.yaml`, `docs/validation_playbook/index.md`, `docs/runbooks/STRAT-EXP-01.md`, `reports/governance/runbook_changelog.md`）。Tests: `pytest tests/unit/test_experiment_tracker.py tests/integration/test_research_experiment_cli.py`. Design cross-check: §62.3. |
| `EP11-INC-P1` | 63.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8102 | done | IncidentPostmortemService scaffold + template (`src/ops/postmortem.py`, `docs/templates/postmortem.md`); tests: `pytest tests/unit/test_incident_postmortem_service.py`. |
| `EP11-INC-P2` | 63.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8103 | done | TradeForensicsAnalyzer + ops incident CLI (`src/ops/trade_forensics.py`, `src/interfaces/cli/ops_incident.py`, `src/interfaces/cli/__init__.py`); tests: `pytest tests/unit/test_trade_forensics_analyzer.py tests/integration/test_ops_incident_cli.py`. |
| `EP11-INC-P3` | 63.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8104 | done | Postmortem metrics include detect/contain timings + evidence hash (`src/ops/postmortem.py`, min/max timeline bounds + non-negative clamp), validation playbook + RUN-INC-01 stub; playbook entries normalized (`docs/validation_playbook/AC43_postmortem.yaml`). Tests: `pytest tests/unit/test_incident_postmortem_service.py`. Validation check: `make check-validation`. |
| `EP12-STRESS-P1` | 64.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8164 | done | MarginStressLab + CapitalAllocationGuard + CorrelationGuard simulateでストレス結果とエンベロープ生成、metrics/audit/envelope出力を実装（`src/risk/stress_lab.py`, `src/risk/capital_guard.py`, `src/risk/correlation_guard.py`, `metrics/margin_stress.jsonl`, `logs/audit/margin_stress.jsonl`, `reports/risk/envelopes`）。Envelopeはsafe_dump fallbackでJSON保存に対応。Tests: `pytest tests/unit/test_margin_stress_lab.py tests/unit/test_stress_simulation.py`. Design cross-check: §64.1/§64.2. |
| `EP12-STRESS-P2` | 64.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8165 | done | CLI `tradectl risk stress run/compare` + envelope apply/simulate + presets config + runbook update（`src/interfaces/cli/risk_stress.py`, `src/interfaces/cli/__init__.py`, `config/risk/margin_stress_presets.yaml`, `docs/runbooks/RUN-RISK-01.md`）。レポートのファイル日付はUTCで統一。Tests: `pytest tests/unit/test_risk_stress_cli.py`. Design cross-check: §64.2. |
| `EP12-STRESS-P3` | 64.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8166 | done | 週次レポートへリスクエンベロープ差分サマリを追加（`src/interfaces/cli/report.py`, `src/reporter/templates/weekly_m1_core*.md`）。Design cross-check: §64.3. |
| `EP13-COACH-P1` | 65.3 テレメトリ・ダッシュボード統合・Codex Packet | detailed_design_fx_signal_tool_v1.md:8223 | done | TraderWorkflowTelemetryServiceを実装（`src/telemetry/trader_workflow.py`）し、summary記録を追加。Tests: `pytest tests/unit/test_trader_workflow_telemetry.py`. Design cross-check: §65.1. |
| `EP13-COACH-P2` | 65.3 テレメトリ・ダッシュボード統合・Codex Packet | detailed_design_fx_signal_tool_v1.md:8224 | done | CoachingPlaybook + CLI `ops coaching summary/insight/review/simulate` を追加（`src/ops/coaching.py`, `src/interfaces/cli/ops.py`, `src/interfaces/cli/__init__.py`, `config/coaching_thresholds.yaml`）。Runbook `COACHING-01`連携前提。Tests: `pytest tests/unit/test_coaching_cli.py`. Design cross-check: §65.2. |
| `EP13-COACH-P3` | 65.3 テレメトリ・ダッシュボード統合・Codex Packet | detailed_design_fx_signal_tool_v1.md:8225 | done | Ops dashboardにcoaching指標を追加し週次レポートへcoaching summaryブロックを追加、Validation playbook `AC10_human_performance` を追加（`src/ops/dashboard.py`, `src/interfaces/cli/ops_dashboard.py`, `src/interfaces/cli/report.py`, `src/reporter/templates/weekly_m1_core_extended*.md`, `docs/validation_playbook/AC10_human_performance.yaml`）。Tests: `pytest tests/unit/test_trader_workflow_telemetry.py tests/unit/test_coaching_cli.py`. Design cross-check: §65.3. |
| `EP14-DEGRADE-P1` | 66.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8278 | done | DegradationPlaybookOrchestrator core + metrics/audit/event + validation sync (`src/ops/degradation.py`, `docs/validation_playbook/AC34_degradation.yaml`, `metrics/degradation_playbook.jsonl`, `logs/events/degradation_playbook.jsonl`). Review fixes: unknown scenario guard, evidence existence check, playbook category default, YAML payload dict normalization. Tests: `pytest tests/unit/test_degradation_playbook.py`. Design cross-check: §66.1/§66.2. |
| `EP14-DEGRADE-P2` | 66.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8279 | done | CLI `tradectl ops degrade trigger/status/ack/recover` + evidence ledger連携 (`src/interfaces/cli/degradation.py`, `src/interfaces/cli/__init__.py`). Tests: `pytest tests/integration/test_degradation_cli.py`. Design cross-check: §66.2. |
| `EP14-DEGRADE-P3` | 66.3 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8280 | done | Runbook/Playbook/Schema/Weekly summary整備 (`docs/runbooks/RUN-DEGRADE-01.md`, `docs/validation_playbook/AC34_degradation.yaml`, `docs/schemas/degradation_playbook.schema.json`, `reports/weekly/templates/m1_plus.md`). Validation: `make check-validation`. Design cross-check: §66.3. |
| `EP11-RISKCONSENT-P1` | 67.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8357 | done | RiskDisclosureEnforcer core (`src/compliance/risk_disclosure_enforcer.py`); tests: `pytest tests/unit/test_risk_disclosure_enforcer.py`. |
| `EP11-RISKCONSENT-P2` | 67.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8358 | done | Device binding encrypted registry + CLI `compliance device`/`risk-disclosure enforce` with error exit on binding failure (`src/compliance/device_binding.py`, `src/interfaces/cli/compliance_risk.py`, `src/interfaces/cli/__init__.py`, `pyproject.toml`); tests: `pytest tests/unit/test_device_binding_service.py tests/integration/test_risk_consent_flow.py tests/unit/test_compliance_risk_cli.py`. |
| `EP11-RISKCONSENT-P3` | 67.5 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8359 | done | Risk consent metrics/audit include device_id/consent_reference_id + validation playbook updates (`metrics/risk_consent.jsonl`, `docs/validation_playbook/AC44_risk_consent.yaml`, `docs/runbooks/COMPLIANCE-01.md`); tests: `pytest tests/unit/test_risk_disclosure_enforcer.py`. |
| `EP12-PROMO-P1` | 68.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8422 | done | PromotionChecklistServiceコア（Idea checklist/Experiment/Validation/Risk/Opsの最小統合）+ ExperimentTracker stub loader + manual review更新 (`src/research/promotion.py`, `src/research/experiment.py`)。Idea rootは`research/ideas`に統一し、validation項目は重複登録を避ける。Tests: `pytest tests/unit/test_promotion_checklist.py`. Design cross-check: §68.1. |
| `EP12-PROMO-P2` | 68.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8423 | done | CLI `research promote/checklist` + simulate + override/approval flowの最小実装 (`src/interfaces/cli/research_promote.py`, `src/interfaces/cli/__init__.py`)。サブコマンド実行時に必須オプションを強制しないようcallbackの必須を緩和。Tests: `pytest tests/unit/test_research_promote_cli.py`. Design cross-check: §68.2. |
| `EP12-PROMO-P3` | 68.4 テスト・Codex Packet・受入条件 | detailed_design_fx_signal_tool_v1.md:8424 | done | Promotion metrics/audit/validation/evidence/ops連携 (`metrics/promotion_gate.jsonl`, `docs/validation_playbook/AC46_promotion_gate.yaml`, `logs/events/ops.agenda.jsonl`, `src/research/promotion.py`)。OpsEvidenceStoreはdrill以外のPlaybookは`<id>.yaml`へ記録。Tests: `pytest tests/unit/test_promotion_gate_metrics.py`. Design cross-check: §68.3. |
| `EP14-SUNSET-P1` | 69.4 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8505 | done | StrategySunsetServiceでdirective/plan/execute/complete + metrics/audit/evidence (`src/governance/sunset.py`, `metrics/strategy_sunset.jsonl`, `logs/events/strategy_sunset.jsonl`, `logs/audit/strategy_sunset.jsonl`). Review fix: validation playbook category default, YAML payload dict normalization, evidence missing guard + test. Tests: `pytest tests/unit/test_strategy_sunset_service.py`. Design cross-check: §69.1/§69.2. |
| `EP14-SUNSET-P2` | 69.4 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8506 | done | CLI `tradectl governance sunset issue/plan/execute/complete` + portfolio reallocation suggest (`src/interfaces/cli/governance_sunset.py`, `src/interfaces/cli/portfolio.py`, `src/portfolio/reallocation.py`, `src/interfaces/cli/__init__.py`). Tests: `pytest tests/integration/test_governance_sunset_cli.py tests/integration/test_portfolio_reallocation_cli.py`. Design cross-check: §69.2/§69.3. |
| `EP14-SUNSET-P3` | 69.4 テレメトリ・監査・Codex Packet | detailed_design_fx_signal_tool_v1.md:8507 | done | Runbook/Playbook/index/changelog更新 (`docs/runbooks/STRAT-SUNSET-01.md`, `docs/validation_playbook/AC55_sunset.yaml`, `docs/validation_playbook/index.md`, `reports/governance/runbook_changelog.md`). Validation: `make check-validation`. Design cross-check: §69.4. |
| `EP15-ACCESS-P1` | 70.4 Codex Packet・テスト・受入条件 | detailed_design_fx_signal_tool_v1.md:8575 | done | AccessGovernanceService + CLI `tradectl access`（principals/devices/review/enforce/report）を実装（`src/security/access.py`, `src/interfaces/cli/access.py`, `src/interfaces/cli/__init__.py`）。Review完了/ポリシー突合/レポート生成を含む。Enforceは最新デバイスの決定順序を固定し、隔離デバイスをブロック理由に追加。Review完了時のevidence不足は事前検証でエラー扱いに統一。Tests: `pytest -k access_governance` (0 selected; exit 5; no access tests). |
| `EP15-ACCESS-P2` | 70.4 Codex Packet・テスト・受入条件 | detailed_design_fx_signal_tool_v1.md:8576 | done | Ops Agendaにアクセスレビュー期限超過タスクを追加し、critical_firstのworklog判定はtarget_date基準に調整（`src/ops/agenda.py`）。due_at未設定のレビューも当日タスクとして提示するように補正。Validation playbook `AC44_access` 追加 + index更新、`tools/check_validation_playbook.py` に `--category` フィルタ追加。Tests: `pytest -k ops_agenda_status`; `python3 tools/check_validation_playbook.py --category access`. |
| `EP15-ACCESS-P3` | 70.4 Codex Packet・テスト・受入条件 | detailed_design_fx_signal_tool_v1.md:8577 | done | Runbook `SEC-ACCESS-01` と runbook changelog を追加（`docs/runbooks/SEC-ACCESS-01.md`, `reports/governance/runbook_changelog.md`）。 |
| `EP16-REG-P1` | 78.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:8738 | done | RegressionBacktestSuiteコア + シナリオローダ/結果集計を追加（`src/backtest/regression.py`, `config/regression_scenarios.yaml`, `config/regression.yaml`）。Review fix: no-scenario runs now error, config concurrency/runtime clamped to >=1. Tests: `pytest tests/regression/test_regression_backtest_suite.py`. Tests not rerun for this change. |
| `EP16-REG-P2` | 78.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:8739 | done | CLI `tradectl backtest regression list/run` + tool/Makefile/CI統合（`src/interfaces/cli/backtest_regression.py`, `src/interfaces/cli/__init__.py`, `tools/regression/backtest.py`, `Makefile`, `ci/regression-backtest.yml`）。Ops agenda driftタスク追加（`src/ops/agenda.py`）。Review fix: tool/CLI surface configuration errors for empty scenario set. Tests: `pytest tests/regression/test_regression_backtest_suite.py tests/regression/test_regression_backtest_cli.py`. Tests not rerun for this change. |
| `EP16-REG-P3` | 78.4 テスト計画・Codex Packet | detailed_design_fx_signal_tool_v1.md:8740 | done | Validation playbook `AC13_regression` + index更新、Runbook `STRAT-M1-VALIDATION`へ回帰手順追加、SecureShare profile + change request template + post comment stub追加（`docs/validation_playbook/AC13_regression.yaml`, `docs/validation_playbook/index.md`, `docs/runbooks/STRAT-M1-VALIDATION.md`, `config/share_profiles/research_validation.yaml`, `docs/change_requests/REGRESSION_BUNDLE_TEMPLATE.md`, `tools/regression/post_comment.py`）。Validation check: `python3 tools/check_validation_playbook.py --category regression`. |
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
| `EP04-T1` | 15.4 EP-04 Ticket Clarity（HITL UX） | detailed_design_fx_signal_tool_v1.md:4555 | done | TicketBuilderの構造化/TTL委譲を反映済み。Review fix: fallback metrics select by strategy_id, add hands-off sizing test (`tests/unit/test_ticket_builder_hands_off.py`). |
| `EP04-T2` | 15.4 EP-04 Ticket Clarity（HITL UX） | detailed_design_fx_signal_tool_v1.md:4556 | done | Boardバナー表示と承認確認ダイアログを追加済み。 |
| `EP04-T3` | 15.4 EP-04 Ticket Clarity（HITL UX） | detailed_design_fx_signal_tool_v1.md:4557 | done | 監査delta/consent_reference_id/health/spread情報 + determinism hashの明示指定 + risk_disclosure/二重承認の整合を反映済み。 |
| `EP05-T1` | 15.5 EP-05 Weekly Review（レポート/監査） | detailed_design_fx_signal_tool_v1.md:4566 | done | 週次テンプレへManual CSV/RiskSummary/ops_worklogを統合済み。 |
| `EP05-T2` | 15.5 EP-05 Weekly Review（レポート/監査） | detailed_design_fx_signal_tool_v1.md:4567 | done | Benchmark欠損率判定と`benchmark_gap`イベントを実装済み。 |
| `EP05-T3` | 15.5 EP-05 Weekly Review（レポート/監査） | detailed_design_fx_signal_tool_v1.md:4568 | done | 週次テンプレに署名欄/Manual CSV/Guardrails節を追加済み。 |
| `EP04-P4` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5878 | done | AccountAggregator + CLI `tradectl accounts status/ingest/aggregate/alerts` を実装（`src/accounts/aggregator.py`, `src/interfaces/cli/accounts.py`, `src/interfaces/cli/__init__.py`）。`open_positions`の配列対応と`--tz`反映（tz未指定はUTC）。メトリクス: `metrics/accounts_aggregator.jsonl`。Tests: `pytest tests/unit/test_account_aggregator.py tests/integration/test_accounts_cli.py`. CLI確認: `python3 -m tradectl accounts status --json`. Design cross-check: §29.1/§29.2. |
| `EP05-P6` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5840 | done | AttributionEngine + 週次レポート統合（`src/reporter/attribution.py`, `src/interfaces/cli/report.py`, `src/reporter/templates/weekly_m1_core_attribution.md`, `src/reporter/templates/weekly_m1_core_extended_attribution.md`）。CLIは`tradectl report weekly --with-attribution`。Metrics: `metrics/reports_attribution.jsonl`. Tests: `pytest tests/unit/test_attribution_engine.py tests/integration/test_weekly_report_attribution.py tests/approval/test_weekly_attribution_snapshot.py`. Design cross-check: §28.1/§28.2. |
| `EP05-P7` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5926 | done | AuditBundleServiceで監査パック生成/署名/検証/レポート/メトリクスを整備（`src/audit/bundle.py`, `src/interfaces/cli/__init__.py`）。署名は`audit_manifest.json`のSHA256を対象とし、`--dry-run`時はメトリクス/イベントを抑制。`reports/audit/audit_pack/<period>.md`生成、`metrics/audit_bundle.jsonl`記録。Tests: `pytest tests/unit/test_audit_bundle.py tests/integration/test_audit_bundle_cli.py`. CLI確認: `python3 -m tradectl audit bundle generate --period 2025Q1 --json`, `python3 -m tradectl audit bundle verify --path audit_pack/2025Q1 --json`（missingなし）。Design cross-check: §30.0-§30.2. |
| `EP06-P4` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5805 | done | StrategyManifestValidator + CLI `tradectl strategy manifest *` + ManifestHealthJob builder + metrics (`src/strategies/manifest.py`, `src/interfaces/cli/strategy_manifest.py`, `src/interfaces/cli/__init__.py`)。ResearchManifestリンク/リスク帯域評価を追加し、`config/strategy_manifest.yaml`に`research_manifest`/`risk_band`を反映（`reports/research/manifest_drafts/*.yaml`、`validation_playbook_id`付与）。Research manifest生成CLIに`--validation-playbook`を追加。Playbook `docs/validation_playbook/AC-01.yaml` を新設。Runbook `RES-MANIFEST-01` 更新（v0.2）。Tests: `pytest tests/unit/test_strategy_manifest_validator.py tests/integration/test_strategy_manifest_cli.py`. CLI確認: `python3 -m tradectl research manifest --strategy m1_baseline_ma_rsi --validation-playbook AC-01 --json`, `python3 -m tradectl strategy manifest validate --json`. Design cross-check: §27.1/§27.2. |
| `EP06-P5` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5990 | done | StrategyScoringService + CLI `tradectl strategy score *` + Boardスコア表示を実装（`src/strategies/scoring.py`, `src/interfaces/cli/strategy_scoring.py`, `src/interfaces/cli/board.py`）。Runbook `RES-SCORE-01` 追加（`docs/runbooks/RES-SCORE-01.md`, `reports/governance/runbook_changelog.md`）。Tests: `pytest tests/unit/test_strategy_scoring.py tests/integration/test_board_scores.py`. Design cross-check: §32.1/§32.2（閾値/重みは設計に準拠）。 |
| `EP07-P1` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:5967 | done | ReleaseGateService + CLI `tradectl release prepare/record/verify/tag --dry-run` を実装し、監査ログ/guardrails/メトリクス/イベントを追加（`src/release/gate.py`, `src/interfaces/cli/__init__.py`）。Release audit schema: `docs/schemas/release_audit.schema.json`. Metrics: `metrics/release_gate.jsonl`, audit log: `logs/audit/release_<YYYYMMDD>.jsonl`. Tests: `pytest tests/unit/test_release_gate_service.py tests/integration/test_release_cli.py`. CLI確認: `python3 -m tradectl release prepare --version v1.1.0 --json`, `python3 -m tradectl release record --version v1.1.0 --task risk_state_json_status_accepted_consent_reference_id_accepted_at_consent_reference_id_id --status pass --evidence reports/validation_log/release_status_20260117.json --json`, `python3 -m tradectl release verify --version v1.1.0 --json`（blocked）。Design cross-check: §31.0-§31.2. |
| `EP07-P2` | 57.4 テスト・Codex Packet・移行方針 | detailed_design_fx_signal_tool_v1.md:6018 | done | OpsReadinessServiceを実装し、CLI連携/メトリクス/アラート/レポートを追加（`src/ops/readiness.py`, `src/interfaces/cli/ops.py`）。Metrics: `metrics/ops_readiness.jsonl`. Tests: `pytest tests/unit/test_ops_readiness_service.py tests/integration/test_ops_readiness_cli.py tests/unit/test_ops_readiness_output.py`. CLI確認: `python3 -m tradectl ops readiness --json`（missingなし）。Design cross-check: §33.1/§33.3. |
