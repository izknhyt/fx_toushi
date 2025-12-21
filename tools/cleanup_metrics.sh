#!/usr/bin/env bash
set -euo pipefail

# Cleanup script for metrics logs.
# - raw ingestion logs: gzip after 60 days, delete gz after 90 days
# - SLA snapshots: delete after 120 days

ROOT_DIR="${1:-.}"

find "${ROOT_DIR}/metrics/raw" -type f -name '*.jsonl' -mtime +60 -print0 2>/dev/null | xargs -0 -r gzip
find "${ROOT_DIR}/metrics/raw" -type f -name '*.jsonl.gz' -mtime +90 -print0 2>/dev/null | xargs -0 -r rm -f
find "${ROOT_DIR}/metrics" -maxdepth 1 -type f -name 'data_ingestion_sla.jsonl*' -mtime +120 -print0 2>/dev/null | xargs -0 -r rm -f
