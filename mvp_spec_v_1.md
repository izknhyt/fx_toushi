# FX Operations Simulation Game — MVP Specification (v1)

## 1. Vision
- **Theme**: Operate a Human-in-the-Loop FX signal team during the first release cycle (M1 Core).
- **Player Role**: Ops lead who balances data reliability, risk exposure, and team morale while chasing profitability over a seven-day sprint.
- **Primary Loop**: For each in-game day, respond to a random operational event, select actions across three phases (Morning Ops, Midday Trading, Evening Review), and watch KPIs evolve.
- **Win Condition**: Complete the seven-day sprint with risk under control, data quality acceptable, morale healthy, and cumulative profit on target.

## 2. MVP Goals
1. Provide a fully playable terminal experience with deterministic seeding for reproducible practice runs.
2. Expose at least four distinct action archetypes that mirror real responsibilities from the FX HITL toolchain:
   - Data recovery / catch-up
   - Signal approval / execution oversight
   - Risk mitigation
   - Team care / retrospectives
3. Surface daily incidents representing realistic operational stressors (e.g., data feed outages, market shocks).
4. Track and report the core state variables that map to the real program KPIs:
   - `data_quality` (0–100, higher is better)
   - `risk_load` (0–100, lower is better)
   - `team_morale` (0–100, higher is better)
   - `profit_score` (unbounded integer)
5. Deliver a closing summary that captures the narrative of the run, including the log of actions and incidents.

## 3. Functional Requirements
### FR-01 Game Engine
- Manage a campaign over a fixed number of days (default: 7).
- Each day contains exactly three phases: Morning Ops, Midday Trading, Evening Review.
- Support deterministic randomness via a configurable seed.
- Provide a clean API to query available actions, apply an action, and inspect the resulting state/outcome.

### FR-02 Actions
- Define actions as reusable objects with identifiers, titles, descriptions, and stat deltas.
- Actions may optionally depend on the current state (e.g., capped improvements if KPIs already high).
- Applying an action should append an entry to the timeline log with the delta that was applied.
- Clamp KPI values to the 0–100 range where relevant to avoid runaway stats.

### FR-03 Events
- Trigger exactly one random event at the start of each day.
- Events should describe what happened and apply stat deltas.
- Events respect simple guard conditions (e.g., avoid morale-boost events when morale is already maxed).

### FR-04 Outcome Evaluation
- Loss conditions:
  - `data_quality` < 20
  - `team_morale` < 15
  - `risk_load` >= 90
  - `profit_score` < -30
- Win condition:
  - Finish all seven days **and**
  - `profit_score` >= 40
  - `data_quality` >= 40
  - `team_morale` >= 35
  - `risk_load` < 80
- If none of the loss conditions are triggered and the win condition is unmet after the final phase, the player receives a neutral outcome.

### FR-05 CLI Experience
- Implement a `tradectl-game` console script that walks the player through the simulation.
- Display at minimum: current day/phase, KPI table, day-opening event narrative (if any), action menu, and result messages.
- Provide a concise end-of-run report summarizing KPIs and listing the timeline log.
- Offer `--seed` and `--days` options for experimentation (days must remain >= 3).

## 4. Non-Functional Requirements
- Pure Python 3.11, no third-party runtime dependencies.
- Modular code to allow reuse of the engine in future GUI or automated tests.
- Provide unit tests that cover action application, event triggering, and win/loss evaluation boundaries.
- Code must be documented with doctrings and type hints for public objects.

## 5. Future Enhancements (Out of Scope for MVP)
- Multiple difficulty presets (Easy/Normal/Hard).
- Persistence of campaign history to disk.
- Rich terminal UI (colors/layout) or web/GUI front end.
- Additional KPI dimensions (e.g., compliance score, benchmark delta).
- AI advisor for recommending actions.

