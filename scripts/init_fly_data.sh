#!/usr/bin/env bash
# Populate the homebidder_data volume on Fly with all required datasets.
# Run this ONCE after the first deploy, then re-run with --force to refresh.
#
# Usage:
#   ./scripts/init_fly_data.sh            # skip already-downloaded files
#   ./scripts/init_fly_data.sh --force    # re-download everything

set -euo pipefail

APP="homebidder-api"
FORCE="${1:-}"

echo "==> Waking up $APP machine..."
flyctl machine start --app "$APP" 2>/dev/null || true
# Give the machine a few seconds to reach the running state
sleep 5

echo "==> Downloading CA hazard GeoJSON + market datasets on $APP..."
flyctl ssh console --app "$APP" -C "python3 /app/scripts/prefetch_backend_data.py ${FORCE}"

echo "==> Downloading CalEnviroScreen 4.0 GeoJSON on $APP..."
flyctl ssh console --app "$APP" -C "python3 /app/scripts/download_calenviroscreen.py ${FORCE}"

echo "==> Done. Data volume is populated."
