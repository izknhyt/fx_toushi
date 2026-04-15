# FX Portfolio Development Team

Status: active development workflow reference  
Last updated: 2026-03-19  
Parent architecture: [FX Portfolio Operating System](/Users/izumimotohayato/development/codex_invest/docs/architecture/fx_portfolio_operating_system.md)  
Implementation spec: [FX Portfolio Tool v2 Specification](/Users/izumimotohayato/development/codex_invest/docs/architecture/fx_portfolio_tool_v2_spec.md)

## 1. Purpose

この文書は、`codex_invest` を portfolio-first に育てるための最適な開発チーム構成を定義する。

狙いは次の 4 点:

1. 長めの開発タスクを clean ownership で並列化する
2. `allocator -> runtime -> validation -> GUI/shadow -> ops` の contract 崩れを減らす
3. spec / evidence / docs 更新を task 完了条件へ固定する
4. 個人利用の repo でも、複数 agent による自動開発を安全に回す

## 2. Principles

- `portfolio-first`
- `single decision path`
- `clean ownership`
- `shared contract stewardship`
- `evidence before promotion`
- `bugcheck on every task`

補足:

- 並列化の単位は「ファイル」ではなく「責務境界」で切る
- `allocation.py` と `registry.py` の境界は最も壊れやすいので、同時変更は強く管理する
- GUI と shadow は close だが、`可視化` と `日次監視ロジック` は別 role に分ける

## 3. Team Topology

### 3.1 Core Integrator

主責務:

- architecture judgment
- task decomposition
- agent assignment
- final integration
- final bugcheck
- `docs/development_plan.md` の整合維持

原則:

- critical path の design decision は Core Integrator が持つ
- 各 agent の成果をそのまま採用せず、contract と tests を見て統合する

### 3.2 Allocator Core Agent

主担当:

- [allocation.py](/Users/izumimotohayato/development/codex_invest/src/strategies/allocation.py)
- [candidate.py](/Users/izumimotohayato/development/codex_invest/src/strategies/candidate.py)
- allocation profile / admission scoring metadata

得意な作業:

- `role_priority`
- `slot_cost`
- `exposure_bucket`
- `AllocationOutcome`
- tie-break / defer / replace semantics

競合注意:

- `registry.py` の event flow 変更
- candidate schema 変更
- reason code 変更

### 3.3 Runtime & Simulation Agent

主担当:

- [registry.py](/Users/izumimotohayato/development/codex_invest/src/strategies/registry.py)
- [paper_poc.py](/Users/izumimotohayato/development/codex_invest/src/backtest/paper_poc.py)

得意な作業:

- `last_run_candidate_trades`
- `last_run_allocation_outcomes`
- `portfolio.admission` event flow
- open positions / account state propagation
- parity in backtest

競合注意:

- allocator contract 変更
- event schema 変更
- position/account model 変更

### 3.4 Validation & Evidence Agent

主担当:

- [run_long_horizon_portfolio_validation.py](/Users/izumimotohayato/development/codex_invest/tools/run_long_horizon_portfolio_validation.py)
- [review_long_horizon_validation.py](/Users/izumimotohayato/development/codex_invest/tools/review_long_horizon_validation.py)
- [evaluate_portfolio_candidates.py](/Users/izumimotohayato/development/codex_invest/tools/evaluate_portfolio_candidates.py)
- focused validation / tuning runners

得意な作業:

- long-horizon windows
- drag diagnosis
- marginal contribution evaluation
- focused rerun optimization

競合注意:

- candidate/admission schema 変更
- CLI surface 変更

### 3.5 Portfolio GUI / Shadow Surface Agent

主担当:

- [allocation_surface.py](/Users/izumimotohayato/development/codex_invest/src/interfaces/gui/allocation_surface.py)
- [candidate_surface.py](/Users/izumimotohayato/development/codex_invest/src/interfaces/gui/candidate_surface.py)
- [web_server.py](/Users/izumimotohayato/development/codex_invest/src/interfaces/gui/web_server.py)
- [shadow_api.py](/Users/izumimotohayato/development/codex_invest/src/interfaces/gui/shadow_api.py)
- [gui_ops_loop.py](/Users/izumimotohayato/development/codex_invest/tools/gui_ops_loop.py)
- [app.js](/Users/izumimotohayato/development/codex_invest/ui/web/app.js)

得意な作業:

- candidate / admission 可視化
- conflict rendering
- occupancy / reason breakdown
- winner bias / review summary

競合注意:

- event name 変更
- shadow summary contract 変更
- allocator payload shape 変更

### 3.6 Shadow Monitoring & Drift Agent

主担当:

- [shadow_baseline.py](/Users/izumimotohayato/development/codex_invest/src/interfaces/gui/shadow_baseline.py)
- [shadow_daily_review.py](/Users/izumimotohayato/development/codex_invest/src/interfaces/gui/shadow_daily_review.py)
- [shadow_daily_history.py](/Users/izumimotohayato/development/codex_invest/src/interfaces/gui/shadow_daily_history.py)
- [shadow_daily_alerts.py](/Users/izumimotohayato/development/codex_invest/src/interfaces/gui/shadow_daily_alerts.py)
- [shadow_daily_ops.py](/Users/izumimotohayato/development/codex_invest/src/interfaces/gui/shadow_daily_ops.py)

得意な作業:

- drift / missed fill monitoring
- history and trend logic
- alert thresholds
- daily shadow summaries

競合注意:

- shadow API contract 変更
- broker shadow schema 変更
- ops summary payload 変更

### 3.7 Ops Agenda & Automation Agent

主担当:

- [agenda.py](/Users/izumimotohayato/development/codex_invest/src/ops/agenda.py)
- [render_daily_shadow_ops_summary.py](/Users/izumimotohayato/development/codex_invest/tools/render_daily_shadow_ops_summary.py)
- `logs/ops/*` consumer flow

得意な作業:

- alert to task routing
- lightweight notification routing
- daily ops agenda integration
- operational phrasing / priority tuning

競合注意:

- agenda item schema 変更
- notification payload 変更
- shadow alert contract 変更

## 4. Shared Contract Stewardship

次の変更は、単独 agent に閉じず Core Integrator が統合する。

- `CandidateTrade` field 追加/改名
- `portfolio.admission` payload 変更
- `reason_code` 変更
- `shadow_*_summary` payload 変更
- `tradectl portfolio ...` の JSON/Markdown contract 変更

特に壊れやすい境界:

1. `allocation.py` ↔ `registry.py`
2. `registry.py` ↔ GUI/shadow consumers
3. validation tools ↔ CLI wrapper
4. shadow summary helpers ↔ ops agenda routing

## 5. Default Parallel Workflow

長時間タスクは、原則として次の順で回す。

1. Core Integrator が task を 2-4 本の独立 slice に切る
2. slice ごとに agent を割り当てる
3. agent は自分の ownership 範囲だけを変更する
4. Core Integrator が contract 変更の有無を確認する
5. 必要な cross-cutting patch を最後に統合する
6. `$task-bugcheck` を回す
7. `docs/development_plan.md` と update log を更新する

## 6. When To Parallelize

並列化してよい:

- validation tool と GUI surface の同時改善
- shadow monitoring と ops agenda routing の同時改善
- CLI wrapper と report generator の同時改善
- evidence runner と docs 更新の分離

並列化しない方がよい:

- `allocation.py` と `registry.py` を同時に別 agent が大きく触る変更
- candidate schema / admission schema の改名
- same payload を複数 consumer が同時に更新する変更
- architecture decision そのものが未確定な変更

## 7. Required Skills Per Role

- Allocator Core Agent: [$portfolio-parity](/Users/izumimotohayato/.codex/skills/portfolio-parity/SKILL.md), [$portfolio-runtime](/Users/izumimotohayato/.codex/skills/portfolio-runtime/SKILL.md)
- Runtime & Simulation Agent: [$portfolio-runtime](/Users/izumimotohayato/.codex/skills/portfolio-runtime/SKILL.md), [$task-bugcheck](/Users/izumimotohayato/.codex/skills/task-bugcheck/SKILL.md)
- Validation & Evidence Agent: [$candidate-onboarding](/Users/izumimotohayato/.codex/skills/candidate-onboarding/SKILL.md), [$long-horizon-review](/Users/izumimotohayato/.codex/skills/long-horizon-review/SKILL.md)
- Portfolio GUI / Shadow Surface Agent: [$portfolio-gui](/Users/izumimotohayato/.codex/skills/portfolio-gui/SKILL.md), [$portfolio-parity](/Users/izumimotohayato/.codex/skills/portfolio-parity/SKILL.md)
- Ops Agenda & Automation Agent: [$task-bugcheck](/Users/izumimotohayato/.codex/skills/task-bugcheck/SKILL.md)
- Core Integrator: all of the above as needed

## 8. Definition of Done For A Team Task

team task は、次の条件を満たして初めて done とする。

1. ownership 境界をまたぐ contract 変更が明示されている
2. 該当 skill に沿った最小回帰 bundle を実行している
3. `$task-bugcheck` を dry-run ではなく run まで回している
4. evidence path を `docs/development_plan.md` に記録している
5. update log を UTC minute 単位で追記している

## 9. Default Team For Current Phase

現フェーズでは、次の 5 役を既定チームとする。

1. `Core Integrator`
2. `Allocator Core Agent`
3. `Validation & Evidence Agent`
4. `Portfolio GUI / Shadow Surface Agent`
5. `Shadow Monitoring & Drift Agent`

必要時のみ追加:

- `Runtime & Simulation Agent`
- `Ops Agenda & Automation Agent`

理由:

- 今の repo の主戦場は `portfolio admission`, `validation evidence`, `GUI/shadow observability`, `shadow monitoring`
- `paper_poc` や agenda は常に触るわけではないので、常設より on-demand の方が衝突が少ない
