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

echo "==> Downloading CA hazard GeoJSON + market datasets on $APP..."
flyctl ssh console --app "$APP" -C "cd /app && python3 scripts/prefetch_backend_data.py ${FORCE}"

echo "==> Downloading CalEnviroScreen 4.0 GeoJSON on $APP..."
flyctl ssh console --app "$APP" -C "cd /app && python3 scripts/download_calenviroscreen.py ${FORCE}"

echo "==> Done. Data volume is populated."
