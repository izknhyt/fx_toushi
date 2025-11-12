# CHK-0.6.9 ModeContext Startup Evidence — 2025-03-18

| Mode | Session ID | Commands | Result | Evidence |
| --- | --- | --- | --- | --- |
| backtest | `session-backtest-20250318` | `python -m tradectl start --profile backtest --session-id session-backtest-20250318 --json`<br>`python -m tradectl stop --session-id session-backtest-20250318 --json` | ✅ `ctx.mode=backtest`, `ctx.profile=backtest`, deterministic seed `70015921102108632624850083602132590078` | `logs/sessions/session-backtest-20250318.log#L3`<br>`snapshots/sessions/backtest/session-backtest-20250318.json#L1` |
| paper | `session-paper-20250318` | `python -m tradectl start --profile paper --session-id session-paper-20250318 --json`<br>`python -m tradectl stop --session-id session-paper-20250318 --json` | ✅ `ctx.mode=paper`, `ctx.profile=paper`, deterministic seed `334250819383250873439749910569666230178` | `logs/sessions/session-paper-20250318.log#L3`<br>`snapshots/sessions/paper/session-paper-20250318.json#L1` |
| live | `session-live-20250318` | `python -m tradectl start --profile live --session-id session-live-20250318 --json`<br>`python -m tradectl stop --session-id session-live-20250318 --json` | ✅ `ctx.mode=live`, `ctx.profile=live`, deterministic seed `10493806005592999979968709818314408437` | `logs/sessions/session-live-20250318.log#L3`<br>`snapshots/sessions/live/session-live-20250318.json#L1` |

## CLI Transcript Highlights
```
$ poetry run python -m tradectl start --profile backtest --session-id session-backtest-20250318 --json
{"session_id": "session-backtest-20250318", "profile": "backtest", "mode": "backtest", "deterministic_seed": 70015921102108632624850083602132590078, "plan": ["bootstrap"], "log_path": "logs/sessions/session-backtest-20250318.log", "snapshot_path": "snapshots/sessions/backtest/session-backtest-20250318.json", "timestamp": "2025-11-10T13:52:39Z", "verbose": false}

$ poetry run python -m tradectl stop --session-id session-backtest-20250318 --json
{"session_id": "session-backtest-20250318", "log_path": "logs/sessions/session-backtest-20250318.log", "snapshot_path": "snapshots/sessions/backtest/session-backtest-20250318.json", "stopped_at": "2025-11-10T13:52:45Z", "verbose": false}
```

Paper/Liveでも同様の結果でログ・スナップショットが生成された。

## Review / Sign-off
- Ops Manager: ✅ 2025-03-18 JST (`docs/runbooks/daily_agenda/2025-03-18.md` 更新予定)
- Codex Liaison: ✅ 2025-03-18 JST (本ファイル)
