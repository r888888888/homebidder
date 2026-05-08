"""Tests for POST/GET/DELETE /api/seen-properties endpoints."""

import datetime
import pytest
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
        listing = Listing(
            address_input=address,
            address_matched=address.upper(),
        )
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


# ---------------------------------------------------------------------------
# POST /api/seen-properties
# ---------------------------------------------------------------------------

async def test_mark_seen_yes_persists_composite_score_one(client):
    """POST with bidding_intent='yes' returns composite_score=1.0."""
    token, user_id = await _register_and_login(client, "yes@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "bidding_intent": "yes"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["analysis_id"] == analysis_id
    assert data["bidding_intent"] == "yes"
    assert data["composite_score"] == pytest.approx(1.0)


async def test_mark_seen_no_persists_composite_score_zero(client):
    """POST with bidding_intent='no' returns composite_score=0.0."""
    token, user_id = await _register_and_login(client, "no@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "bidding_intent": "no"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["bidding_intent"] == "no"
    assert data["composite_score"] == pytest.approx(0.0)


async def test_mark_seen_omits_quality_and_location_uses_defaults(client):
    """POST without quality/location succeeds (server defaults to 'neutral')."""
    token, user_id = await _register_and_login(client, "defaults@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "bidding_intent": "yes"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    # Server stores neutral defaults so the legacy NOT NULL columns are satisfied.
    assert data["quality"] == "neutral"
    assert data["location"] == "neutral"


async def test_mark_seen_requires_bidding_intent(client):
    """POST without bidding_intent returns 422."""
    token, user_id = await _register_and_login(client, "missing@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_mark_seen_invalid_bidding_intent_returns_422(client):
    """POST with bidding_intent='maybe' (or any non-yes/no) returns 422."""
    token, user_id = await _register_and_login(client, "maybe@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    for bad in ("maybe", "true", "Yes", ""):
        resp = await client.post(
            "/api/seen-properties",
            json={"analysis_id": analysis_id, "bidding_intent": bad},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422, f"Expected 422 for bidding_intent={bad!r}"


async def test_mark_seen_requires_auth(client):
    """POST without authentication returns 401."""
    analysis_id = await _seed_analysis()
    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "bidding_intent": "yes"},
    )
    assert resp.status_code == 401


async def test_mark_seen_duplicate_returns_409(client):
    """Marking the same analysis seen twice returns 409."""
    token, user_id = await _register_and_login(client, "dup@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)
    payload = {"analysis_id": analysis_id, "bidding_intent": "yes"}

    resp1 = await client.post(
        "/api/seen-properties", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp1.status_code == 201
    resp2 = await client.post(
        "/api/seen-properties", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp2.status_code == 409


async def test_mark_seen_analysis_not_found_returns_404(client):
    """POST with a nonexistent analysis_id returns 404."""
    token, _ = await _register_and_login(client, "notfound@test.com")
    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": 99999, "bidding_intent": "yes"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_mark_seen_with_notes(client):
    """POST with optional notes stores them correctly."""
    token, user_id = await _register_and_login(client, "notes@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "bidding_intent": "yes", "notes": "Nice yard"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["notes"] == "Nice yard"


# ---------------------------------------------------------------------------
# GET /api/seen-properties
# ---------------------------------------------------------------------------

async def test_list_seen_properties(client):
    """GET returns all seen properties for the authenticated user."""
    token, user_id = await _register_and_login(client, "listtest@test.com")
    analysis_id_1 = await _seed_analysis(user_id=user_id, address="100 A St, SF, CA 94110")
    analysis_id_2 = await _seed_analysis(user_id=user_id, address="200 B St, SF, CA 94110")

    for aid in (analysis_id_1, analysis_id_2):
        await client.post(
            "/api/seen-properties",
            json={"analysis_id": aid, "bidding_intent": "yes"},
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get("/api/seen-properties", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["seen_properties"]) == 2
    # bidding_intent is round-tripped on the list response.
    assert all("bidding_intent" in row for row in data["seen_properties"])


async def test_list_seen_properties_requires_auth(client):
    """GET without auth returns 401."""
    resp = await client.get("/api/seen-properties")
    assert resp.status_code == 401


async def test_list_seen_by_analysis_id(client):
    """GET ?analysis_id=X returns only the matching row (or empty)."""
    token, user_id = await _register_and_login(client, "filtertest@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "bidding_intent": "yes"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/api/seen-properties?analysis_id={analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    rows = resp.json()["seen_properties"]
    assert len(rows) == 1
    assert rows[0]["analysis_id"] == analysis_id
    assert rows[0]["bidding_intent"] == "yes"


async def test_list_seen_cross_user_isolation(client):
    """User A cannot see User B's seen properties."""
    token_a, user_id_a = await _register_and_login(client, "usera@test.com")
    token_b, user_id_b = await _register_and_login(client, "userb@test.com")

    analysis_id = await _seed_analysis(user_id=user_id_a)
    await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "bidding_intent": "yes"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    resp = await client.get("/api/seen-properties", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    assert len(resp.json()["seen_properties"]) == 0


# ---------------------------------------------------------------------------
# DELETE /api/seen-properties/{id}
# ---------------------------------------------------------------------------

async def test_delete_seen_property(client):
    """DELETE removes the seen property row."""
    token, user_id = await _register_and_login(client, "deltest@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    create_resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "bidding_intent": "yes"},
        headers={"Authorization": f"Bearer {token}"},
    )
    seen_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/seen-properties/{seen_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 200

    list_resp = await client.get("/api/seen-properties", headers={"Authorization": f"Bearer {token}"})
    assert len(list_resp.json()["seen_properties"]) == 0


async def test_delete_cross_user_returns_403(client):
    """User B cannot delete User A's seen property."""
    token_a, user_id_a = await _register_and_login(client, "ownerx@test.com")
    token_b, _ = await _register_and_login(client, "intruder@test.com")

    analysis_id = await _seed_analysis(user_id=user_id_a)
    create_resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "bidding_intent": "yes"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    seen_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/seen-properties/{seen_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert del_resp.status_code == 403


async def test_delete_requires_auth(client):
    """DELETE without auth returns 401."""
    resp = await client.delete("/api/seen-properties/999")
    assert resp.status_code == 401
