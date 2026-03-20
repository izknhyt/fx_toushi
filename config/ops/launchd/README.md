# launchd setup (macOS)

This directory contains launchd service definitions for local ops.

## Execution dashboard (every 6 hours)

1. Copy the plist:
   - `cp config/ops/launchd/com.codex.execution-dashboard.plist ~/Library/LaunchAgents/`
2. Load it:
   - `launchctl load ~/Library/LaunchAgents/com.codex.execution-dashboard.plist`
3. Check logs:
   - `logs/ops/execution_dashboard.log`

## Shadow next-stage daily automation (every day at 09:15 JST)

1. Copy the plist:
   - `cp config/ops/launchd/com.codex.shadow-next-stage.plist ~/Library/LaunchAgents/`
2. Load it:
   - `launchctl load ~/Library/LaunchAgents/com.codex.shadow-next-stage.plist`
3. Check logs:
   - `logs/ops/shadow_next_stage_daily.log`
   - `logs/ops/shadow_next_stage_daily.err.log`
4. Equivalent manual command:
   - `bash tools/scripts/run_shadow_next_stage_daily.sh --run`
   - fallback: `python3 tools/scripts/run_shadow_next_stage_daily.py --run`

## Cron example

- Reference file: `config/ops/shadow_next_stage_daily.cron`
- Equivalent manual command:
  - `bash tools/scripts/run_shadow_next_stage_daily.sh --run`
  - fallback: `python3 tools/scripts/run_shadow_next_stage_daily.py --run`

## Apply rate_limit.env to launchd

If you run `tradectl` via launchd, apply the env once:

1. Run:
   - `bash tools/scripts/apply_rate_limit_env_launchd.sh config/ops/rate_limit.env`
2. For launchd jobs, add an `EnvironmentVariables` block if you want it embedded.

## Auto-apply rate_limit.env at login (recommended)

1. Copy the plist:
   - `cp config/ops/launchd/com.codex.rate-limit-env.plist ~/Library/LaunchAgents/`
2. Load it:
   - `launchctl load ~/Library/LaunchAgents/com.codex.rate-limit-env.plist`
3. Confirm:
   - `launchctl getenv TRADECTL_RATE_LIMIT_TPM`
