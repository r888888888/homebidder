"""
Tests for the subscription-tier-aware monthly rate limiting system.

Anonymous users: 3 analyses/month (RateLimitEntry, monthly window)
Buyer tier:      5 analyses/month (counted from analyses table)
Investor tier:  30 analyses/month (counted from analyses table)
Agent tier:    100 analyses/month (counted from analyses table)
Superusers:    unlimited

Grandfathered users share the Investor limit.
"""

import datetime
import hashlib
import os
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from db import engine
from db.models import Analysis, Listing, RateLimitEntry, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _mock_run_agent(address, buyer_context="", db=None, force_refresh=False, user_id=None):
    import json
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


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


async def _set_user_tier(user_id: str, tier: str, is_grandfathered: bool = False) -> None:
    """Directly update a user's subscription_tier in the test DB."""
    from sqlalchemy import text
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(
            text(
                "UPDATE users SET subscription_tier = :tier, is_grandfathered = :gf "
                "WHERE id = :uid"
            ),
            {"tier": tier, "gf": 1 if is_grandfathered else 0, "uid": user_id},
        )
        await session.commit()


async def _set_superuser(user_id: str) -> None:
    from sqlalchemy import text
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(
            text("UPDATE users SET is_superuser = 1 WHERE id = :uid"),
            {"uid": user_id},
        )
        await session.commit()


async def _seed_analyses(user_id: str, count: int, days_ago: float = 0.0) -> None:
    """Seed Analysis rows for a user with a given age (days from now)."""
    ts = datetime.datetime.utcnow() - datetime.timedelta(days=days_ago)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        listing = Listing(address_input="seed", address_matched="SEED")
        session.add(listing)
        await session.flush()
        for i in range(count):
            session.add(
                Analysis(
                    listing_id=listing.id,
                    session_id=f"seed-{i}",
                    user_id=user_id,
                    created_at=ts,
                )
            )
        await session.commit()


async def _seed_anon_entries(ip: str, count: int, days_ago: float = 0.0) -> None:
    """Seed RateLimitEntry rows for an anonymous IP with a given age."""
    identifier = _hash_ip(ip)
    ts = datetime.datetime.utcnow() - datetime.timedelta(days=days_ago)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        for _ in range(count):
            session.add(RateLimitEntry(identifier=identifier, created_at=ts))
        await session.commit()


# ---------------------------------------------------------------------------
# Anonymous users — 3/month
# ---------------------------------------------------------------------------

async def test_anonymous_user_allowed_3_per_month(client):
    """Anonymous users can run up to 3 analyses in a calendar month."""
    with patch("api.routes.run_agent", _mock_run_agent):
        for _ in range(3):
            resp = await client.post(
                "/api/analyze",
                json={"address": "450 Sanchez St, SF, CA 94114"},
                headers={"Fly-Client-IP": "10.1.0.1"},
            )
            assert resp.status_code == 200


async def test_anonymous_user_blocked_on_4th_this_month(client):
    """4th anonymous analysis in the same month returns 429."""
    await _seed_anon_entries("10.1.0.2", count=3)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Fly-Client-IP": "10.1.0.2"},
        )
    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["code"] == "MONTHLY_LIMIT_REACHED"
    assert detail["tier"] == "anonymous"
    assert detail["upgrade_url"] == "/register"


async def test_anonymous_prior_month_entries_dont_count(client):
    """Entries from the previous month are outside the window and don't block."""
    # Seed 3 entries from 35 days ago (previous month)
    await _seed_anon_entries("10.1.0.3", count=3, days_ago=35)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Fly-Client-IP": "10.1.0.3"},
        )
    assert resp.status_code == 200


async def test_anonymous_rate_limit_status_monthly_window(client):
    """Rate-limit status for anonymous users reports monthly window and tier."""
    await _seed_anon_entries("10.1.0.4", count=2)
    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Fly-Client-IP": "10.1.0.4"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["used"] == 2
    assert data["limit"] == 3
    assert data["remaining"] == 1
    assert data["window"] == "monthly"
    assert data["tier"] == "anonymous"


# ---------------------------------------------------------------------------
# Buyer tier — 5/month
# ---------------------------------------------------------------------------

async def test_buyer_user_allowed_5_per_month(client):
    """Buyer tier users can run up to 5 analyses per month."""
    token, user_id = await _register_and_login(client, "buyer1@test.com")
    # new users start as buyer; seed 4 existing analyses
    await _seed_analyses(user_id, count=4)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200


async def test_buyer_user_blocked_after_5_analyses_this_month(client):
    """Buyer tier blocked on the 6th analysis this month."""
    token, user_id = await _register_and_login(client, "buyer2@test.com")
    await _seed_analyses(user_id, count=5)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["code"] == "MONTHLY_LIMIT_REACHED"
    assert detail["tier"] == "buyer"
    assert detail["limit"] == 5


# ---------------------------------------------------------------------------
# Investor tier — 30/month
# ---------------------------------------------------------------------------

async def test_investor_user_blocked_after_30_analyses_this_month(client):
    """Investor tier blocked on the 31st analysis this month."""
    token, user_id = await _register_and_login(client, "investor1@test.com")
    await _set_user_tier(user_id, "investor")
    await _seed_analyses(user_id, count=30)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["tier"] == "investor"
    assert detail["limit"] == 30


async def test_investor_user_not_blocked_before_limit(client):
    """Investor tier with 29 analyses this month can still run one more."""
    token, user_id = await _register_and_login(client, "investor2@test.com")
    await _set_user_tier(user_id, "investor")
    await _seed_analyses(user_id, count=29)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Agent tier — 100/month
# ---------------------------------------------------------------------------

async def test_agent_user_blocked_after_100_analyses_this_month(client):
    """Agent tier blocked on the 101st analysis this month."""
    token, user_id = await _register_and_login(client, "agent1@test.com")
    await _set_user_tier(user_id, "agent")
    await _seed_analyses(user_id, count=100)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["tier"] == "agent"
    assert detail["limit"] == 100


# ---------------------------------------------------------------------------
# Grandfathered users — treated as Investor
# ---------------------------------------------------------------------------

async def test_grandfathered_user_treated_as_investor(client):
    """A grandfathered buyer-tier user gets the Investor limit (30/month)."""
    token, user_id = await _register_and_login(client, "gf1@test.com")
    # Grandfathered but subscription_tier is still 'buyer'
    await _set_user_tier(user_id, "buyer", is_grandfathered=True)
    await _seed_analyses(user_id, count=30)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Authorization": f"Bearer {token}"},
        )
    # 31st analysis should be blocked at the Investor limit (30)
    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["limit"] == 30


# ---------------------------------------------------------------------------
# Prior month analyses don't count
# ---------------------------------------------------------------------------

async def test_prior_month_analyses_dont_count(client):
    """Analyses from the previous calendar month are outside the window."""
    token, user_id = await _register_and_login(client, "monthly1@test.com")
    # Seed 5 analyses from 35 days ago (previous month)
    await _seed_analyses(user_id, count=5, days_ago=35)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Superuser — unlimited
# ---------------------------------------------------------------------------

async def test_superuser_is_never_rate_limited(client):
    """Superusers bypass the rate limit entirely."""
    token, user_id = await _register_and_login(client, "super1@test.com")
    await _set_superuser(user_id)
    # Seed way over the Buyer limit
    await _seed_analyses(user_id, count=50)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Rate-limit status for authenticated users
# ---------------------------------------------------------------------------

async def test_rate_limit_status_authenticated_monthly_window(client):
    """Authenticated user status reports monthly window, tier, and correct counts."""
    token, user_id = await _register_and_login(client, "status1@test.com")
    await _seed_analyses(user_id, count=3)
    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["used"] == 3
    assert data["limit"] == 5          # buyer default
    assert data["remaining"] == 2
    assert data["window"] == "monthly"
    assert data["tier"] == "buyer"


async def test_rate_limit_status_investor_limit(client):
    """Investor tier status reports limit=30."""
    token, user_id = await _register_and_login(client, "status2@test.com")
    await _set_user_tier(user_id, "investor")
    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()
    assert data["limit"] == 30
    assert data["tier"] == "investor"
