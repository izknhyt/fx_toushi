# Agent Rules

All work should follow these rules.

## Required Review
- At the start of each task, open and review `docs/development_plan.md`.

## Required Updates
- After completing any implementation or changes, update `docs/development_plan.md` in the same patch:
  - Unified Task Table status and notes
  - Design Alignment Backlog status and notes
  - Implementation Review Checklist items completed

## Start Checklist
- Open `docs/development_plan.md`.
- Confirm the task you are about to work on is reflected in the Unified Task Table or Backlog.
- Note any evidence/test commands you expect to run.

## Finish Checklist
- Update `docs/development_plan.md` with status/notes/evidence.
- Tick the Implementation Review Checklist items completed.
- If you ran tests or generated evidence, note the paths in the notes.
- Append a new entry to the Update Log with UTC time to the minute.
  - Use `make update-log MSG="..."` or `python3 tools/update_log.py "..."`.
