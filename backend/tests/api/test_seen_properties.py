"""Tests for POST/GET/DELETE /api/seen-properties endpoints."""

import datetime
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from db import engine
from db.models import Analysis, Listing


# ---------------------------------------------------------------------------
# Helpers (duplicated from test_auth_analysis.py — no shared fixtures across
# test files to keep test isolation simple)
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

async def test_mark_seen_creates_record(client):
    """POST with valid data creates a seen_property and returns composite_score."""
    token, user_id = await _register_and_login(client, "mark@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "quality": "good", "location": "good"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["analysis_id"] == analysis_id
    assert data["quality"] == "good"
    assert data["location"] == "good"
    assert pytest.approx(data["composite_score"]) == pytest.approx(0.875)  # (0.75+1.0)/2


async def test_mark_seen_requires_auth(client):
    """POST without authentication returns 401."""
    analysis_id = await _seed_analysis()
    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "quality": "good", "location": "good"},
    )
    assert resp.status_code == 401


async def test_mark_seen_invalid_quality_returns_422(client):
    """POST with an invalid quality string returns 422."""
    token, user_id = await _register_and_login(client, "badquality@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "quality": "fantastic", "location": "good"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_mark_seen_invalid_location_returns_422(client):
    """POST with an invalid location string returns 422."""
    token, user_id = await _register_and_login(client, "badloc@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "quality": "good", "location": "amazing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_mark_seen_duplicate_returns_409(client):
    """Marking the same analysis seen twice returns 409."""
    token, user_id = await _register_and_login(client, "dup@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)
    payload = {"analysis_id": analysis_id, "quality": "good", "location": "good"}

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
        json={"analysis_id": 99999, "quality": "good", "location": "good"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_mark_seen_with_notes(client):
    """POST with optional notes stores them correctly."""
    token, user_id = await _register_and_login(client, "notes@test.com")
    analysis_id = await _seed_analysis(user_id=user_id)

    resp = await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "quality": "neutral", "location": "neutral", "notes": "Nice yard"},
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
            json={"analysis_id": aid, "quality": "good", "location": "neutral"},
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get("/api/seen-properties", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["seen_properties"]) == 2


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
        json={"analysis_id": analysis_id, "quality": "good", "location": "good"},
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


async def test_list_seen_cross_user_isolation(client):
    """User A cannot see User B's seen properties."""
    token_a, user_id_a = await _register_and_login(client, "usera@test.com")
    token_b, user_id_b = await _register_and_login(client, "userb@test.com")

    analysis_id = await _seed_analysis(user_id=user_id_a)
    await client.post(
        "/api/seen-properties",
        json={"analysis_id": analysis_id, "quality": "good", "location": "good"},
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
        json={"analysis_id": analysis_id, "quality": "good", "location": "good"},
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
        json={"analysis_id": analysis_id, "quality": "good", "location": "good"},
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
