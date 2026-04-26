#!/usr/bin/env bash
# Forward Stripe webhooks to the local backend.
# Usage: ./stripe-listen.sh [backend-port]
#
# Requires the Stripe CLI: brew install stripe/stripe-cli/stripe
# First-time setup: stripe login

set -euo pipefail

PORT="${1:-8000}"
TARGET="http://localhost:${PORT}/api/payments/webhook"

if ! command -v stripe &>/dev/null; then
  echo "stripe CLI not found. Install it with:"
  echo "  brew install stripe/stripe-cli/stripe"
  exit 1
fi

echo "Forwarding Stripe webhooks → ${TARGET}"
echo "Copy the whsec_... secret printed below into your .env as STRIPE_WEBHOOK_SECRET"
echo ""

stripe listen --forward-to "${TARGET}"
