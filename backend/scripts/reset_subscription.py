#!/usr/bin/env python3
"""
Reset a user's subscription to the free Buyer tier for local testing.

Cancels their Stripe subscription and resets their DB fields so they can
go through the upgrade flow again from scratch.

Usage:
    python3 backend/scripts/reset_subscription.py <email>
    python3 backend/scripts/reset_subscription.py <email> --delete-customer
    python3 backend/scripts/reset_subscription.py <email> --dry-run

Options:
    --delete-customer  Also delete the Stripe Customer record so the next
                       checkout creates a fresh one (tests first-checkout path).
    --dry-run          Print what would happen without making any changes.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow imports from backend/
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

import os
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{BACKEND_DIR}/homebidder.db")

import stripe
from sqlalchemy import select

from config import settings
from db import SessionLocal
from db.models import User


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


async def reset_user(email: str, delete_customer: bool, dry_run: bool) -> None:
    if not settings.stripe_secret_key:
        print("ERROR: STRIPE_SECRET_KEY is not set — check your .env file.")
        sys.exit(1)

    stripe.api_key = settings.stripe_secret_key

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            print(f"ERROR: No user found with email: {email}")
            sys.exit(1)

        print(f"User:                  {user.email}")
        print(f"  subscription_tier:   {user.subscription_tier}")
        print(f"  subscription_status: {user.subscription_status}")
        print(f"  stripe_customer_id:  {user.stripe_customer_id}")
        print(f"  stripe_sub_id:       {user.stripe_subscription_id}")
        print()

        if dry_run:
            print("[dry-run] Would perform the following actions:")
            if user.stripe_subscription_id:
                print(f"  - Cancel Stripe subscription {user.stripe_subscription_id}")
            if delete_customer and user.stripe_customer_id:
                print(f"  - Delete Stripe customer {user.stripe_customer_id}")
            print(f"  - Set subscription_tier → 'buyer'")
            print(f"  - Set stripe_subscription_id → null")
            print(f"  - Set subscription_status → null")
            if delete_customer:
                print(f"  - Set stripe_customer_id → null")
            print("\n[dry-run] No changes made.")
            return

        # Cancel Stripe subscription
        if user.stripe_subscription_id:
            try:
                stripe.Subscription.cancel(user.stripe_subscription_id)
                print(f"Cancelled Stripe subscription {user.stripe_subscription_id}")
            except stripe.error.InvalidRequestError as e:
                # Already cancelled or doesn't exist — fine for testing
                print(f"Warning: could not cancel subscription: {e.user_message}")
        else:
            print("No Stripe subscription on record — skipping cancellation.")

        # Delete Stripe customer (optional)
        if delete_customer:
            if user.stripe_customer_id:
                try:
                    stripe.Customer.delete(user.stripe_customer_id)
                    print(f"Deleted Stripe customer {user.stripe_customer_id}")
                except stripe.error.InvalidRequestError as e:
                    print(f"Warning: could not delete customer: {e.user_message}")
            else:
                print("No Stripe customer on record — skipping customer deletion.")

        # Reset DB
        user.subscription_tier = "buyer"
        user.stripe_subscription_id = None
        user.subscription_status = None
        if delete_customer:
            user.stripe_customer_id = None

        session.add(user)
        await session.commit()

        print(f"\nDone. {email} has been reset to Buyer tier.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset a user's subscription to Buyer tier for local testing."
    )
    parser.add_argument("email", help="Email address of the user to downgrade")
    parser.add_argument(
        "--delete-customer",
        action="store_true",
        help="Also delete the Stripe Customer record (tests first-checkout path)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without making any changes",
    )
    args = parser.parse_args()

    asyncio.run(reset_user(args.email, args.delete_customer, args.dry_run))


if __name__ == "__main__":
    main()
