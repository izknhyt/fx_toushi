#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  exec "$ROOT/.venv/bin/python" tools/scripts/run_v2_completion_check_daily.py "$@"
fi

if command -v poetry >/dev/null 2>&1; then
  exec poetry run python tools/scripts/run_v2_completion_check_daily.py "$@"
fi

exec python3 tools/scripts/run_v2_completion_check_daily.py "$@"
