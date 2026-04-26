"""Stripe payment routes.

POST /api/payments/create-checkout-session  — initiate a subscription upgrade
GET  /api/payments/customer-portal          — link to Stripe billing portal
POST /api/payments/webhook                  — handle Stripe webhook events
"""

import logging
import uuid

import stripe
from stripe import SignatureVerificationError
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from config import settings
from db import get_db
from db.models import User

log = logging.getLogger(__name__)

payments_router = APIRouter(prefix="/payments", tags=["payments"])


def _stripe_configured() -> bool:
    return bool(settings.stripe_secret_key)


def _valid_price_ids() -> set[str]:
    ids = set()
    if settings.stripe_investor_price_id:
        ids.add(settings.stripe_investor_price_id)
    if settings.stripe_agent_price_id:
        ids.add(settings.stripe_agent_price_id)
    return ids


def _tier_for_price_id(price_id: str) -> str:
    """Map a Stripe price ID to the subscription tier string."""
    if price_id == settings.stripe_agent_price_id:
        return "agent"
    return "investor"


# ---------------------------------------------------------------------------
# Request body
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    price_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@payments_router.post("/create-checkout-session")
async def create_checkout_session(
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Create a Stripe Checkout session for upgrading to Investor or Agent tier.

    Returns ``{"url": "<hosted Stripe Checkout URL>"}`` which the frontend
    redirects to.  No Stripe.js / embedded elements needed.
    """
    if not _stripe_configured():
        raise HTTPException(status_code=503, detail="Payment system not configured.")

    valid = _valid_price_ids()
    if body.price_id not in valid:
        raise HTTPException(status_code=400, detail="Unknown price ID.")

    stripe.api_key = settings.stripe_secret_key

    # Create a Stripe Customer the first time, then reuse it.
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": str(user.id)},
        )
        user.stripe_customer_id = customer.id
        db.add(user)
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        line_items=[{"price": body.price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.frontend_url}/profile?checkout=success",
        cancel_url=f"{settings.frontend_url}/pricing",
        client_reference_id=str(user.id),
        subscription_data={
            "metadata": {"price_id": body.price_id},
        },
    )
    return {"url": session.url}


@payments_router.get("/customer-portal")
async def customer_portal(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Return a Stripe billing portal URL so the user can manage their subscription."""
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found.")

    stripe.api_key = settings.stripe_secret_key or ""

    portal = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.frontend_url}/profile",
    )
    return {"url": portal.url}


@payments_router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle incoming Stripe webhook events.

    Supported events:
    - checkout.session.completed  → upgrade user to Investor/Agent tier
    - customer.subscription.updated → sync subscription_status
    - customer.subscription.deleted → downgrade user to Buyer tier
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = settings.stripe_webhook_secret

    if not webhook_secret:
        # Dev mode with no webhook secret — skip verification.
        try:
            import json
            event = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except SignatureVerificationError as exc:
            log.warning("Stripe webhook signature verification failed: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(obj, db)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(obj, db)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(obj, db)
    else:
        log.debug("Stripe webhook: unhandled event type %s", event_type)

    return {"received": True}


# ---------------------------------------------------------------------------
# Webhook event handlers
# ---------------------------------------------------------------------------

async def _handle_checkout_completed(obj: dict, db: AsyncSession) -> None:
    """Upgrade user to the purchased tier after a successful Stripe Checkout."""
    user_id_str = obj.get("client_reference_id")
    customer_id = obj.get("customer")
    subscription_id = obj.get("subscription")

    if not user_id_str:
        log.warning("checkout.session.completed missing client_reference_id")
        return

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        log.warning("checkout.session.completed: invalid UUID %s", user_id_str)
        return

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        log.warning("checkout.session.completed: user %s not found", user_id_str)
        return

    # Determine tier from price_id stored in subscription metadata, if present.
    price_id = obj.get("metadata", {}).get("price_id", "")
    tier = _tier_for_price_id(price_id) if price_id else "investor"

    user.stripe_customer_id = customer_id
    user.stripe_subscription_id = subscription_id
    user.subscription_tier = tier
    user.subscription_status = "active"
    db.add(user)
    await db.commit()
    log.info("Upgraded user %s to %s tier", user_id_str, tier)


async def _handle_subscription_updated(obj: dict, db: AsyncSession) -> None:
    """Sync subscription_status when Stripe reports a subscription change."""
    subscription_id = obj.get("id")
    status = obj.get("status")

    if not subscription_id:
        return

    result = await db.execute(
        select(User).where(User.stripe_subscription_id == subscription_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        log.debug("subscription.updated: no user found for sub %s", subscription_id)
        return

    user.subscription_status = status
    db.add(user)
    await db.commit()
    log.info("Updated subscription status for user %s → %s", user.id, status)


async def _handle_subscription_deleted(obj: dict, db: AsyncSession) -> None:
    """Downgrade user to Buyer tier when their subscription is cancelled."""
    subscription_id = obj.get("id")

    if not subscription_id:
        return

    result = await db.execute(
        select(User).where(User.stripe_subscription_id == subscription_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        log.debug("subscription.deleted: no user found for sub %s", subscription_id)
        return

    user.subscription_tier = "buyer"
    user.subscription_status = "canceled"
    user.stripe_subscription_id = None
    db.add(user)
    await db.commit()
    log.info("Downgraded user %s to buyer tier (subscription canceled)", user.id)
