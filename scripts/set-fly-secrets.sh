#!/usr/bin/env bash
# Reads .env and sets Fly.io secrets for the backend app, skipping frontend-only
# and local-only variables.
#
# Usage: ./scripts/set-fly-secrets.sh [--app <app-name>]
#
# Defaults to the app name in fly.toml (homebidder-api).

set -euo pipefail

APP="${1:-homebidder-api}"
ENV_FILE="$(dirname "$0")/../.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: .env file not found at $ENV_FILE" >&2
  exit 1
fi

# Variables to skip — either frontend-only or overridden in fly.toml
SKIP=(
  VITE_API_URL
  DATABASE_URL
  LOG_FILE
)

args=()

while IFS= read -r line || [[ -n "$line" ]]; do
  # Skip blank lines and comments
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

  # Extract key (everything before the first =)
  key="${line%%=*}"
  key="${key// /}"  # trim spaces

  # Skip keys in the exclusion list
  skip=false
  for s in "${SKIP[@]}"; do
    [[ "$key" == "$s" ]] && skip=true && break
  done
  $skip && continue

  args+=("$line")
done < "$ENV_FILE"

if [[ ${#args[@]} -eq 0 ]]; then
  echo "No secrets to set."
  exit 0
fi

echo "Setting ${#args[@]} secret(s) on app '$APP'..."
flyctl secrets set --app "$APP" "${args[@]}"
echo "Done."
