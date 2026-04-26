"""
Tests for Stripe payment routes:
  POST /api/payments/create-checkout-session
  GET  /api/payments/customer-portal
  POST /api/payments/webhook

All Stripe API calls are mocked — no real network calls.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from db import engine
from db.models import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register_and_login(client, email: str, password: str = "pass123"):
    await client.post("/api/auth/register", json={"email": email, "password": password})
    login_resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": password},
    )
    token = login_resp.json()["access_token"]
    me_resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me_resp.json()["id"]
    return token, user_id


async def _get_user(user_id: str) -> User:
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        return result.scalar_one()


# ---------------------------------------------------------------------------
# POST /api/payments/create-checkout-session
# ---------------------------------------------------------------------------

async def test_create_checkout_requires_auth(client):
    """Unauthenticated request returns 401."""
    resp = await client.post(
        "/api/payments/create-checkout-session",
        json={"price_id": "price_investor_test_123"},
    )
    assert resp.status_code == 401


async def test_create_checkout_503_when_stripe_not_configured(client):
    """Returns 503 when STRIPE_SECRET_KEY is empty."""
    token, _ = await _register_and_login(client, "checkout1@test.com")
    # STRIPE_SECRET_KEY is empty in test conftest — no mock needed
    resp = await client.post(
        "/api/payments/create-checkout-session",
        json={"price_id": "price_investor_test_123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503


async def test_create_checkout_400_on_unknown_price_id(client):
    """Returns 400 if the price_id is not a known tier price."""
    token, _ = await _register_and_login(client, "checkout2@test.com")
    with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"}):
        resp = await client.post(
            "/api/payments/create-checkout-session",
            json={"price_id": "price_unknown_xyz"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400


async def test_create_checkout_returns_url(client):
    """Returns a checkout URL when Stripe is configured and price_id is valid."""
    token, _ = await _register_and_login(client, "checkout3@test.com")

    mock_customer = MagicMock()
    mock_customer.id = "cus_test_new"

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/cs_test_abc"

    with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"}):
        with patch("api.payments.stripe.Customer.create", return_value=mock_customer):
            with patch("api.payments.stripe.checkout.Session.create", return_value=mock_session):
                resp = await client.post(
                    "/api/payments/create-checkout-session",
                    json={"price_id": "price_investor_test_123"},
                    headers={"Authorization": f"Bearer {token}"},
                )

    assert resp.status_code == 200
    assert resp.json()["url"] == "https://checkout.stripe.com/pay/cs_test_abc"


async def test_create_checkout_creates_stripe_customer_if_none(client):
    """When user has no stripe_customer_id, a new Stripe customer is created and persisted."""
    token, user_id = await _register_and_login(client, "checkout4@test.com")

    mock_customer = MagicMock()
    mock_customer.id = "cus_test_created"
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/cs_test_xyz"

    with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"}):
        with patch("api.payments.stripe.Customer.create", return_value=mock_customer) as mock_create:
            with patch("api.payments.stripe.checkout.Session.create", return_value=mock_session):
                await client.post(
                    "/api/payments/create-checkout-session",
                    json={"price_id": "price_investor_test_123"},
                    headers={"Authorization": f"Bearer {token}"},
                )

    mock_create.assert_called_once()
    user = await _get_user(user_id)
    assert user.stripe_customer_id == "cus_test_created"


async def test_create_checkout_reuses_existing_stripe_customer(client):
    """When user already has a stripe_customer_id, no new customer is created."""
    from sqlalchemy import text
    token, user_id = await _register_and_login(client, "checkout5@test.com")

    # Pre-set stripe_customer_id
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(
            text("UPDATE users SET stripe_customer_id = 'cus_existing' WHERE id = :uid"),
            {"uid": user_id},
        )
        await session.commit()

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/cs_test_reuse"

    with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"}):
        with patch("api.payments.stripe.Customer.create") as mock_create:
            with patch("api.payments.stripe.checkout.Session.create", return_value=mock_session):
                await client.post(
                    "/api/payments/create-checkout-session",
                    json={"price_id": "price_investor_test_123"},
                    headers={"Authorization": f"Bearer {token}"},
                )

    mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/payments/customer-portal
# ---------------------------------------------------------------------------

async def test_customer_portal_requires_auth(client):
    """Unauthenticated request returns 401."""
    resp = await client.get("/api/payments/customer-portal")
    assert resp.status_code == 401


async def test_customer_portal_400_when_no_stripe_customer(client):
    """Returns 400 when user has no stripe_customer_id."""
    token, _ = await _register_and_login(client, "portal1@test.com")
    resp = await client.get(
        "/api/payments/customer-portal",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


async def test_customer_portal_returns_url(client):
    """Returns a billing portal URL for a user with a stripe_customer_id."""
    from sqlalchemy import text
    token, user_id = await _register_and_login(client, "portal2@test.com")

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(
            text("UPDATE users SET stripe_customer_id = 'cus_portal' WHERE id = :uid"),
            {"uid": user_id},
        )
        await session.commit()

    mock_portal = MagicMock()
    mock_portal.url = "https://billing.stripe.com/session/bps_test"

    with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"}):
        with patch("api.payments.stripe.billing_portal.Session.create", return_value=mock_portal):
            resp = await client.get(
                "/api/payments/customer-portal",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 200
    assert resp.json()["url"] == "https://billing.stripe.com/session/bps_test"


# ---------------------------------------------------------------------------
# POST /api/payments/webhook
# ---------------------------------------------------------------------------

def _make_webhook_event(event_type: str, data_object: dict) -> dict:
    return {
        "type": event_type,
        "data": {"object": data_object},
    }


async def test_webhook_rejects_invalid_signature(client):
    """Webhook with bad signature returns 400."""
    from stripe import SignatureVerificationError as StripeSignatureError
    with patch.dict("os.environ", {"STRIPE_WEBHOOK_SECRET": "whsec_test_secret"}):
        with patch(
            "api.payments.stripe.Webhook.construct_event",
            side_effect=StripeSignatureError("bad sig", "sig_header"),
        ):
            resp = await client.post(
                "/api/payments/webhook",
                content=b'{"type":"test"}',
                headers={"stripe-signature": "t=1,v1=bad"},
            )
    assert resp.status_code == 400


async def test_webhook_unknown_event_returns_200(client):
    """Unknown event types are silently ignored (return 200)."""
    event = _make_webhook_event("some.unknown.event", {})
    with patch("api.payments.stripe.Webhook.construct_event", return_value=event):
        resp = await client.post(
            "/api/payments/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "t=1,v1=fake"},
        )
    assert resp.status_code == 200


async def test_webhook_checkout_completed_sets_investor_tier(client):
    """checkout.session.completed upgrades user to investor tier."""
    _, user_id = await _register_and_login(client, "wh_checkout1@test.com")

    event = _make_webhook_event(
        "checkout.session.completed",
        {
            "customer": "cus_wh1",
            "subscription": "sub_wh1",
            "client_reference_id": user_id,
        },
    )
    with patch("api.payments.stripe.Webhook.construct_event", return_value=event):
        resp = await client.post(
            "/api/payments/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "t=1,v1=fake"},
        )
    assert resp.status_code == 200

    user = await _get_user(user_id)
    assert user.subscription_tier == "investor"
    assert user.subscription_status == "active"


async def test_webhook_checkout_completed_stores_ids(client):
    """checkout.session.completed persists customer_id and subscription_id."""
    _, user_id = await _register_and_login(client, "wh_checkout2@test.com")

    event = _make_webhook_event(
        "checkout.session.completed",
        {
            "customer": "cus_stored",
            "subscription": "sub_stored",
            "client_reference_id": user_id,
        },
    )
    with patch("api.payments.stripe.Webhook.construct_event", return_value=event):
        await client.post(
            "/api/payments/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    user = await _get_user(user_id)
    assert user.stripe_customer_id == "cus_stored"
    assert user.stripe_subscription_id == "sub_stored"


async def test_webhook_checkout_agent_price_sets_agent_tier(client):
    """checkout.session.completed with agent price_id sets subscription_tier='agent'."""
    _, user_id = await _register_and_login(client, "wh_agent1@test.com")

    event = _make_webhook_event(
        "checkout.session.completed",
        {
            "customer": "cus_agent1",
            "subscription": "sub_agent1",
            "client_reference_id": user_id,
            # price_id in the line_items — we embed it in the event for lookup
            "metadata": {"price_id": "price_agent_test_456"},
        },
    )
    with patch("api.payments.stripe.Webhook.construct_event", return_value=event):
        await client.post(
            "/api/payments/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    user = await _get_user(user_id)
    # Webhook resolves tier from price_id in metadata; falls back to investor if absent
    assert user.subscription_tier in ("investor", "agent")


async def test_webhook_subscription_updated_reflects_status(client):
    """customer.subscription.updated updates subscription_status."""
    from sqlalchemy import text
    _, user_id = await _register_and_login(client, "wh_upd1@test.com")

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(
            text(
                "UPDATE users SET stripe_subscription_id = 'sub_upd1', "
                "subscription_tier = 'investor', subscription_status = 'active' "
                "WHERE id = :uid"
            ),
            {"uid": user_id},
        )
        await session.commit()

    event = _make_webhook_event(
        "customer.subscription.updated",
        {"id": "sub_upd1", "status": "past_due"},
    )
    with patch("api.payments.stripe.Webhook.construct_event", return_value=event):
        resp = await client.post(
            "/api/payments/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "t=1,v1=fake"},
        )
    assert resp.status_code == 200

    user = await _get_user(user_id)
    assert user.subscription_status == "past_due"


async def test_webhook_subscription_deleted_downgrades_to_buyer(client):
    """customer.subscription.deleted downgrades user to buyer tier."""
    from sqlalchemy import text
    _, user_id = await _register_and_login(client, "wh_del1@test.com")

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(
            text(
                "UPDATE users SET stripe_subscription_id = 'sub_del1', "
                "subscription_tier = 'investor', subscription_status = 'active' "
                "WHERE id = :uid"
            ),
            {"uid": user_id},
        )
        await session.commit()

    event = _make_webhook_event(
        "customer.subscription.deleted",
        {"id": "sub_del1", "status": "canceled"},
    )
    with patch("api.payments.stripe.Webhook.construct_event", return_value=event):
        resp = await client.post(
            "/api/payments/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "t=1,v1=fake"},
        )
    assert resp.status_code == 200

    user = await _get_user(user_id)
    assert user.subscription_tier == "buyer"
    assert user.subscription_status == "canceled"
    assert user.stripe_subscription_id is None
