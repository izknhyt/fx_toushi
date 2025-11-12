# CHK-0.6.9 ModeContext Startup Evidence — 2025-03-17

| Mode | Session ID | Commands | Result | Evidence |
| --- | --- | --- | --- | --- |
| backtest | `session-backtest-20250317` | `python -m tradectl start --profile backtest --session-id session-backtest-20250317`<br>`python -m tradectl stop --session-id session-backtest-20250317` | ✅ `ctx.mode=backtest`, `ctx.profile=backtest`, deterministic seed `169716764434005338861258488513830107265` | `logs/sessions/session-backtest-20250317.log#L3`<br>`snapshots/sessions/backtest/session-backtest-20250317.json#L1` |
| paper | `session-paper-20250317` | `python -m tradectl start --profile paper --session-id session-paper-20250317`<br>`python -m tradectl stop --session-id session-paper-20250317` | ✅ `ctx.mode=paper`, `ctx.profile=paper`, deterministic seed `126527723148961580171776902497113837280` | `logs/sessions/session-paper-20250317.log#L3`<br>`snapshots/sessions/paper/session-paper-20250317.json#L1` |
| live | `session-live-20250317` | `python -m tradectl start --profile live --session-id session-live-20250317`<br>`python -m tradectl stop --session-id session-live-20250317` | ✅ `ctx.mode=live`, `ctx.profile=live`, deterministic seed `264975844546404237647042043418244723801` | `logs/sessions/session-live-20250317.log#L3`<br>`snapshots/sessions/live/session-live-20250317.json#L1` |

## CLI Transcript Highlights
```
poetry run python -m tradectl start --profile backtest --session-id session-backtest-20250317
→ log_path=logs/sessions/session-backtest-20250317.log
→ snapshot_path=snapshots/sessions/backtest/session-backtest-20250317.json

poetry run python -m tradectl stop --session-id session-backtest-20250317
→ stopped_at=2025-11-09T10:25:44Z
```

同じ手順をPaper/LIVEでも実施し、ログには`ctx.mode`, `ctx.profile`, `deterministic_seed`が全て記録されている。Runbookリンク: `RUN-TIME-01`, `RUN-PERF-01`, `RUN-RISK-01`.

## Review / Sign-off
- Ops Manager: ✅ 2025-03-17 JST (`docs/runbooks/daily_agenda/2025-03-17.md`)
- Codex Liaison: ✅ 2025-03-17 JST (本ファイル)
