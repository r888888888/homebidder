"""Tests for POST/GET/DELETE /api/buying-plan endpoints.

The Buying Plan feature is gated to Investor+ users. It creates a single plan
per user (upsert) and returns plan status derived from the user's seen properties.
"""

import datetime
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from db import engine
from db.models import Analysis, Listing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_analysis(user_id=None, address="1 Test St, San Francisco, CA 94110") -> int:
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        listing = Listing(address_input=address, address_matched=address.upper())
        session.add(listing)
        await session.flush()
        analysis = Analysis(
            listing_id=listing.id,
            session_id="seed-session",
            created_at=datetime.datetime.utcnow(),
            user_id=user_id,
        )
        session.add(analysis)
        await session.commit()
        return analysis.id


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


async def _upgrade_to_investor(user_id: str) -> None:
    """Directly set user's subscription_tier to 'investor' in the DB."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(
            text("UPDATE users SET subscription_tier = 'investor' WHERE id = :id"),
            {"id": user_id},
        )
        await session.commit()


async def _upgrade_to_agent(user_id: str) -> None:
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(
            text("UPDATE users SET subscription_tier = 'agent' WHERE id = :id"),
            {"id": user_id},
        )
        await session.commit()


_BUY_BY = "2026-12-01"
_BASE_PAYLOAD = {"buy_by_date": _BUY_BY, "viewings_per_week": 3.0}
_AUTH = lambda token: {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /api/buying-plan
# ---------------------------------------------------------------------------

async def test_create_plan_requires_auth(client):
    """Unauthenticated POST returns 401."""
    resp = await client.post("/api/buying-plan", json=_BASE_PAYLOAD)
    assert resp.status_code == 401


async def test_create_plan_buyer_forbidden(client):
    """Buyer-tier user cannot create a plan (403)."""
    token, _ = await _register_and_login(client, "buyer@test.com")
    # New accounts are 'buyer' by default
    resp = await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))
    assert resp.status_code == 403


async def test_create_plan_investor_allowed(client):
    """Investor-tier user can create a buying plan."""
    token, user_id = await _register_and_login(client, "investor@test.com")
    await _upgrade_to_investor(user_id)

    resp = await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["plan"]["buy_by_date"] == _BUY_BY
    assert data["plan"]["viewings_per_week"] == 3.0
    assert data["plan"]["total_n"] > 0
    assert data["plan"]["explore_threshold"] >= 1


async def test_create_plan_agent_allowed(client):
    """Agent-tier user can create a buying plan."""
    token, user_id = await _register_and_login(client, "agent@test.com")
    await _upgrade_to_agent(user_id)

    resp = await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))
    assert resp.status_code == 201


async def test_create_plan_includes_status(client):
    """POST response includes plan status (phase, bid_premium_pct)."""
    token, user_id = await _register_and_login(client, "investor2@test.com")
    await _upgrade_to_investor(user_id)

    resp = await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))
    assert resp.status_code == 201
    data = resp.json()
    assert "status" in data
    assert data["status"]["phase"] in ("explore", "commit")
    assert "bid_premium_pct" in data["status"]


async def test_create_plan_upserts_existing(client):
    """A second POST replaces the existing plan (one plan per user)."""
    token, user_id = await _register_and_login(client, "upsert@test.com")
    await _upgrade_to_investor(user_id)

    resp1 = await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))
    assert resp1.status_code == 201
    plan_id_1 = resp1.json()["plan"]["id"]

    resp2 = await client.post(
        "/api/buying-plan",
        json={"buy_by_date": "2027-06-01", "viewings_per_week": 2.0},
        headers=_AUTH(token),
    )
    assert resp2.status_code == 201
    assert resp2.json()["plan"]["viewings_per_week"] == 2.0
    assert resp2.json()["plan"]["buy_by_date"] == "2027-06-01"

    # Only one plan should exist for this user (GET reflects the updated plan).
    get_resp = await client.get("/api/buying-plan", headers=_AUTH(token))
    assert get_resp.json()["plan"]["viewings_per_week"] == 2.0


async def test_create_plan_invalid_date_returns_422(client):
    """POST with a non-date string returns 422."""
    token, user_id = await _register_and_login(client, "baddate@test.com")
    await _upgrade_to_investor(user_id)

    resp = await client.post(
        "/api/buying-plan",
        json={"buy_by_date": "not-a-date", "viewings_per_week": 3.0},
        headers=_AUTH(token),
    )
    assert resp.status_code == 422


async def test_create_plan_invalid_viewings_returns_422(client):
    """POST with zero viewings_per_week returns 422."""
    token, user_id = await _register_and_login(client, "zeroval@test.com")
    await _upgrade_to_investor(user_id)

    resp = await client.post(
        "/api/buying-plan",
        json={"buy_by_date": _BUY_BY, "viewings_per_week": 0},
        headers=_AUTH(token),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/buying-plan
# ---------------------------------------------------------------------------

async def test_get_plan_requires_auth(client):
    """Unauthenticated GET returns 401."""
    resp = await client.get("/api/buying-plan")
    assert resp.status_code == 401


async def test_get_plan_not_found(client):
    """GET when no plan exists returns 404."""
    token, user_id = await _register_and_login(client, "noplan@test.com")
    await _upgrade_to_investor(user_id)
    resp = await client.get("/api/buying-plan", headers=_AUTH(token))
    assert resp.status_code == 404


async def test_get_plan_returns_plan_and_status(client):
    """GET returns the plan + status after creation."""
    token, user_id = await _register_and_login(client, "getplan@test.com")
    await _upgrade_to_investor(user_id)

    await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))

    resp = await client.get("/api/buying-plan", headers=_AUTH(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"]["buy_by_date"] == _BUY_BY
    assert data["status"]["phase"] == "explore"
    assert data["status"]["seen_count"] == 0
    assert "seen_properties" in data


async def test_get_plan_status_reflects_seen_properties(client):
    """Status seen_count increments as properties are marked seen, and a Yes
    intent flips explore_max_score to 1.0."""
    token, user_id = await _register_and_login(client, "withseen@test.com")
    await _upgrade_to_investor(user_id)

    await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))

    analysis_id = await _seed_analysis(user_id=uuid.UUID(user_id), address="5 Seen St, SF, CA 94110")
    await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "bidding_intent": "yes"},
        headers=_AUTH(token),
    )

    resp = await client.get("/api/buying-plan", headers=_AUTH(token))
    body = resp.json()
    assert body["status"]["seen_count"] == 1
    # Binary: any Yes during explore → explore_max_score = 1.0
    assert body["status"]["explore_max_score"] == pytest.approx(1.0)
    # bidding_intent round-trips on the seen_properties payload.
    assert body["seen_properties"][0]["bidding_intent"] == "yes"


async def test_get_plan_status_no_intent_does_not_qualify(client):
    """A 'no' bidding intent does not raise explore_max_score off zero."""
    token, user_id = await _register_and_login(client, "withno@test.com")
    await _upgrade_to_investor(user_id)

    await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))

    analysis_id = await _seed_analysis(user_id=uuid.UUID(user_id), address="6 No St, SF, CA 94110")
    await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "bidding_intent": "no"},
        headers=_AUTH(token),
    )

    resp = await client.get("/api/buying-plan", headers=_AUTH(token))
    assert resp.json()["status"]["explore_max_score"] == pytest.approx(0.0)


async def test_get_plan_buyer_can_still_get(client):
    """A buyer who was downgraded after plan creation can still read their plan."""
    # This tests that GET doesn't gate on tier — only POST does.
    token, user_id = await _register_and_login(client, "downgraded@test.com")
    await _upgrade_to_investor(user_id)
    await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))

    # "downgrade" back to buyer
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(
            text("UPDATE users SET subscription_tier = 'buyer' WHERE id = :id"),
            {"id": user_id},
        )
        await session.commit()

    resp = await client.get("/api/buying-plan", headers=_AUTH(token))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /api/buying-plan
# ---------------------------------------------------------------------------

async def test_delete_plan_requires_auth(client):
    """Unauthenticated DELETE returns 401."""
    resp = await client.delete("/api/buying-plan")
    assert resp.status_code == 401


async def test_delete_plan_not_found(client):
    """DELETE when no plan exists returns 404."""
    token, user_id = await _register_and_login(client, "delnone@test.com")
    await _upgrade_to_investor(user_id)
    resp = await client.delete("/api/buying-plan", headers=_AUTH(token))
    assert resp.status_code == 404


async def test_delete_plan_removes_plan(client):
    """DELETE removes the plan; subsequent GET returns 404."""
    token, user_id = await _register_and_login(client, "delok@test.com")
    await _upgrade_to_investor(user_id)

    await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))
    del_resp = await client.delete("/api/buying-plan", headers=_AUTH(token))
    assert del_resp.status_code == 200

    get_resp = await client.get("/api/buying-plan", headers=_AUTH(token))
    assert get_resp.status_code == 404


async def test_delete_plan_cross_user_isolation(client):
    """User B cannot delete User A's plan."""
    token_a, user_id_a = await _register_and_login(client, "owner@test.com")
    token_b, _ = await _register_and_login(client, "intruder@test.com")
    await _upgrade_to_investor(user_id_a)

    await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token_a))

    # user B has no plan, so should get 404
    del_resp = await client.delete("/api/buying-plan", headers=_AUTH(token_b))
    assert del_resp.status_code == 404

    # user A's plan should still exist
    get_resp = await client.get("/api/buying-plan", headers=_AUTH(token_a))
    assert get_resp.status_code == 200


# ---------------------------------------------------------------------------
# PATCH /api/buying-plan  (pause / resume)
# ---------------------------------------------------------------------------

async def test_patch_plan_requires_auth(client):
    """Unauthenticated PATCH returns 401."""
    resp = await client.patch("/api/buying-plan", json={"is_paused": True})
    assert resp.status_code == 401


async def test_patch_plan_not_found(client):
    """PATCH when no plan exists returns 404."""
    token, user_id = await _register_and_login(client, "patchnone@test.com")
    await _upgrade_to_investor(user_id)
    resp = await client.patch("/api/buying-plan", json={"is_paused": True}, headers=_AUTH(token))
    assert resp.status_code == 404


async def test_patch_plan_pauses_plan(client):
    """PATCH with is_paused=True sets the plan to paused."""
    token, user_id = await _register_and_login(client, "pauseplan@test.com")
    await _upgrade_to_investor(user_id)

    await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))
    resp = await client.patch("/api/buying-plan", json={"is_paused": True}, headers=_AUTH(token))

    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"]["is_paused"] is True


async def test_patch_plan_resumes_plan(client):
    """PATCH with is_paused=False re-enables a paused plan."""
    token, user_id = await _register_and_login(client, "resumeplan@test.com")
    await _upgrade_to_investor(user_id)

    await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))
    await client.patch("/api/buying-plan", json={"is_paused": True}, headers=_AUTH(token))

    resp = await client.patch("/api/buying-plan", json={"is_paused": False}, headers=_AUTH(token))
    assert resp.status_code == 200
    assert resp.json()["plan"]["is_paused"] is False


async def test_get_plan_includes_is_paused_field(client):
    """GET response includes is_paused on the plan object."""
    token, user_id = await _register_and_login(client, "ispaused@test.com")
    await _upgrade_to_investor(user_id)

    await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))
    resp = await client.get("/api/buying-plan", headers=_AUTH(token))

    assert resp.status_code == 200
    assert "is_paused" in resp.json()["plan"]
    assert resp.json()["plan"]["is_paused"] is False


async def test_patch_plan_returns_full_response(client):
    """PATCH returns the full plan + status + seen_properties response."""
    token, user_id = await _register_and_login(client, "patchfull@test.com")
    await _upgrade_to_investor(user_id)

    await client.post("/api/buying-plan", json=_BASE_PAYLOAD, headers=_AUTH(token))
    resp = await client.patch("/api/buying-plan", json={"is_paused": True}, headers=_AUTH(token))

    assert resp.status_code == 200
    data = resp.json()
    assert "plan" in data
    assert "status" in data
    assert "seen_properties" in data
