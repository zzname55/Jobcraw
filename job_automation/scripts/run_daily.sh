#!/usr/bin/env bash
# Daily incremental scrape for cron (Linux/macOS).
# Exports only postings not seen in a previous run.
#
# Add to crontab to run every day at 08:00:
#   0 8 * * * /path/to/job_automation/scripts/run_daily.sh >> /path/to/job_automation/data/logs/cron.log 2>&1
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON="$PROJECT_DIR/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"

"$PYTHON" main.py --region europe --remote true --min-score 60 --new-only true --export all
