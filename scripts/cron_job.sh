#!/usr/bin/env bash
# =============================================================================
# MSU Analytics Daily Ingestion - Linux Cron Runner
# =============================================================================
set -e

# Resolve project directory relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$PROJECT_ROOT/logs"

mkdir -p "$LOGS_DIR"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
echo "[$TIMESTAMP] Starting daily MSU Analytics ingestion job..." >> "$LOGS_DIR/cron_ingestion.log"

cd "$PROJECT_ROOT"

# Activate Python Virtual Environment (if exists)
if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
elif [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Run the master CDC ingestion pipeline and append output to log
python "$PROJECT_ROOT/scripts/run_ingestion.py" >> "$LOGS_DIR/cron_ingestion.log" 2>&1

EXIT_CODE=$?
TIMESTAMP_DONE=$(date +"%Y-%m-%d %H:%M:%S")

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TIMESTAMP_DONE] Job completed SUCCESSFUL (Exit Code: 0)" >> "$LOGS_DIR/cron_ingestion.log"
else
    echo "[$TIMESTAMP_DONE] Job FAILED (Exit Code: $EXIT_CODE)" >> "$LOGS_DIR/cron_ingestion.log"
fi

exit $EXIT_CODE
