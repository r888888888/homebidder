#!/usr/bin/env bash
# Upload local backend/data files to the Fly volume.
# Much faster and more reliable than downloading on the machine.
#
# Usage: ./scripts/upload_fly_data.sh

set -euo pipefail

APP="homebidder-api"
LOCAL_DATA="$(dirname "$0")/../backend/data"

echo "==> Pre-building hazard pkl files locally (avoids ~1.2 GB peak memory on Fly)..."
python3 "$(dirname "$0")/../backend/scripts/build_hazard_pkl.py"

echo "==> Waking up $APP machine..."
flyctl machine start --app "$APP" 2>/dev/null || true
sleep 5

echo "==> Ensuring /app/data directory exists..."
flyctl ssh console --app "$APP" -C "mkdir -p /app/data"

upload() {
  local file="$1"
  local name
  name="$(basename "$file")"
  local size
  size=$(du -sh "$file" | cut -f1)
  echo "  Uploading $name ($size)..."
  cat "$file" | flyctl ssh console --app "$APP" -C "sh -c 'cat > /app/data/$name'"
}

upload "$LOCAL_DATA/redfin_market.tsv.gz"
upload "$LOCAL_DATA/zillow_zhvi.csv"
upload "$LOCAL_DATA/fhfa_hpi.xlsx"
upload "$LOCAL_DATA/fire_hazard_zones.geojson"
upload "$LOCAL_DATA/liquefaction_zones.geojson"
upload "$LOCAL_DATA/ap_fault_zones.geojson"
upload "$LOCAL_DATA/calenviroscreen.geojson"
upload "$LOCAL_DATA/bart_stations.json"
upload "$LOCAL_DATA/muni_stops.json"
upload "$LOCAL_DATA/caltrain_stations.json"
upload "$LOCAL_DATA/schools.json"

echo "==> Uploading pre-built hazard pkl files..."
upload "$LOCAL_DATA/fire_hazard_zones.pkl"
upload "$LOCAL_DATA/liquefaction_zones.pkl"
upload "$LOCAL_DATA/ap_fault_zones.pkl"

echo "==> Done. All data files uploaded to /app/data."
