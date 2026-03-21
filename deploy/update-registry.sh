#!/bin/bash
# Daily registry update — downloads the Latvian business registry CSV
# and imports it into the local SQLite database for company search.
#
# Add to crontab:
#   0 4 * * * /opt/vrekini/deploy/update-registry.sh >> /var/log/vrekini-registry.log 2>&1

set -e

APP_DIR="${APP_DIR:-/opt/vrekini}"
PYTHON="${PYTHON:-$APP_DIR/venv/bin/python}"
DATA_DIR="$APP_DIR/data"
CSV_FILE="$DATA_DIR/register.csv"
CSV_URL="https://dati.ur.gov.lv/register/register.csv"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting registry update..."

# Download the CSV
echo "Downloading $CSV_URL ..."
curl -sS --max-time 600 -o "$CSV_FILE.tmp" "$CSV_URL"

# Verify it's not empty / corrupt
LINE_COUNT=$(wc -l < "$CSV_FILE.tmp")
if [ "$LINE_COUNT" -lt 1000 ]; then
    echo "ERROR: Downloaded file has only $LINE_COUNT lines — likely corrupt. Aborting."
    rm -f "$CSV_FILE.tmp"
    exit 1
fi

mv "$CSV_FILE.tmp" "$CSV_FILE"
echo "Downloaded $LINE_COUNT lines."

# Import into SQLite
cd "$APP_DIR"
VREKINI_REGISTRY_DB_PATH="$DATA_DIR/registry.db" "$PYTHON" -m app.registry "$CSV_FILE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Registry update complete."
