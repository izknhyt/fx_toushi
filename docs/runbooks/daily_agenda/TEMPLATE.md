# <YYYY-MM-DD> Ops Agenda

- **Session**: <Daily Ops / Incident / Sprint Gate>
- **Chair**: <Ops Manager>
- **Attendees**: <Quant Lead / Product Owner / Codex Liaison / Trader Lead>
- **Runbook References**: RUN-TIME-01, RUN-RISK-01, RUN-PERF-01, STRAT-M1-VALIDATION (必要に応じ追加)
- **Related Review Log Entry**: docs/review_log.md#<anchor>

## 1. Opening Checks
| Item | Command / Artifact | Owner | Due | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| Environment health (`CHK-0.6.9-1`) | `poetry install --no-root`<br>`python -m tradectl --help` | Ops Manager | <HH:MM JST> | [ ] Pass [ ] Hold [ ] Fail | Evidence: <link> |
| Smoke tests (`CHK-0.6.9-2`) | `pytest -k smoke` / CI Job ID | Codex Liaison |  |  |  |
| Review packet sync (`CHK-0.6.9-3`) | `docs/review_log.md`, `docs/prompt_packages/` | Quant Lead |  |  |  |
| Risk threshold scaffold (`CHK-0.6.9-4`) | `config/risk_policy.yaml`, `docs/schemas/` | Risk Manager |  |  |  |
| Issue/PR numbering (`CHK-0.6.9-5`) | Codexテンプレ更新状況 | Product Owner |  |  |  |

## 2. ModeContext Startup Walkthrough (`CHK-0.6.9-6/7`)
| Mode | Step | Command / Evidence | Expected Output | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| backtest | Start | `tradectl start --profile backtest` | `ctx.mode=backtest`, `ctx.profile.name=backtest`, deterministic seed logged | [ ] Pass [ ] Hold [ ] Fail | Link: docs/validation/ModeContext_startup.md#1-実行マトリクス |
|  | Stop & Snapshot | `tradectl stop` / `snapshots/sessions/backtest/session-<id>.json` | `SnapshotManager.persist()` log entry |  |  |
| paper | Start | `tradectl start --profile paper` | `ctx.mode=paper`, `ctx.profile.name=paper`, deterministic seed logged |  |  |
| paper | Stop & Snapshot | `tradectl stop` / `snapshots/sessions/paper/session-<id>.json` | `SnapshotManager.persist()` log entry |  |  |
| live | Start | `tradectl start --profile live` | `ctx.mode=live`, `ctx.profile.name=live`, deterministic seed logged |  |  |
| live | Stop & Snapshot | `tradectl stop` / `snapshots/sessions/live/session-<id>.json` | `SnapshotManager.persist()` log entry |  |  |

> 詳細なログ・テスト結果は `docs/validation/ModeContext_startup.md` に追記し、Evidence欄には該当行へのリンクを記載する。

## 3. Ops Agenda Items
| Priority | Topic | Owner | Source | Action | Due | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | <例: Kill Switch review> | <Owner> | RUN-RISK-01 §2 | [ ] ToDo [ ] Doing [ ] Done | <date> |  |
| P1 |  |  |  |  |  |  |
| P2 |  |  |  |  |  |  |

## 4. Codex Hand-off Items
| Item | Description | Evidence | Linked Check ID | Status |
| --- | --- | --- | --- | --- |
| ModeContext Startup Template | `docs/validation/ModeContext_startup.md` 更新 | <commit or PR> | CHK-0.6.9-6, CHK-0.6.9-7 | [ ] Submitted [ ] Reviewed [ ] Closed |
| Codex Issue Checklist | <link to shared doc or repo> |  | CHK-0.6.9-5 |  |

## 5. Decision Log / Next Steps
- **Decisions**:
  - <Decision 1>
  - <Decision 2>
- **Next Review Gate**: <YYYY-MM-DD Event>
- **Follow-up Tickets**:
  - [ ] <ticket-id>: <summary>
  - [ ] <ticket-id>: <summary>

## 6. Sign-off
| Role | Name | Sign-off (timestamp) |
| --- | --- | --- |
| Ops Manager |  |  |
| Product Owner |  |  |
| Quant Lead |  |  |
| Codex Liaison |  |  |
