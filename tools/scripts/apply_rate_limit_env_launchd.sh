#!/bin/bash
set -euo pipefail

ENV_FILE="${1:-config/ops/rate_limit.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "env file not found: $ENV_FILE" >&2
  exit 1
fi

while IFS= read -r line; do
  if [[ -z "$line" ]] || [[ "$line" =~ ^# ]]; then
    continue
  fi
  key="${line%%=*}"
  value="${line#*=}"
  if [[ -z "$key" ]]; then
    continue
  fi
  /bin/launchctl setenv "$key" "$value"
done < "$ENV_FILE"

echo "Applied rate limit env to launchd from $ENV_FILE"
