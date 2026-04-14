"""
Phase 3 tests: profile page — DELETE /api/users/me endpoint.

Covers:
- DELETE /api/users/me removes the user
- DELETE /api/users/me returns 401 when unauthenticated
- DELETE /api/users/me sets analyses' user_id to NULL (ON DELETE SET NULL)
"""
import datetime
import uuid

from db import engine
from db.models import Analysis, Listing, User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select


async def _register_and_login(client, email: str, password: str = "pass123"):
    """Register a new user, log in, and return (token, user_id)."""
    await client.post("/api/auth/register", json={"email": email, "password": password})
    login_resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": password},
    )
    token = login_resp.json()["access_token"]
    me_resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me_resp.json()["id"]
    return token, user_id


async def _seed_analysis_for_user(user_id: str) -> int:
    """Directly insert a Listing + Analysis for a given user_id and return analysis id."""
    uid = uuid.UUID(user_id)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        listing = Listing(
            address_input="9 Profile St, SF, CA 94110",
            address_matched="9 PROFILE ST, SF, CA 94110",
        )
        session.add(listing)
        await session.flush()
        analysis = Analysis(
            listing_id=listing.id,
            session_id="profile-session",
            created_at=datetime.datetime.utcnow(),
            user_id=uid,
        )
        session.add(analysis)
        await session.commit()
        return analysis.id


# ---------------------------------------------------------------------------
# DELETE /api/users/me
# ---------------------------------------------------------------------------

async def test_delete_me_returns_401_when_unauthenticated(client):
    """DELETE /api/users/me without a token returns 401."""
    resp = await client.delete("/api/users/me")
    assert resp.status_code == 401


async def test_delete_me_removes_user(client):
    """DELETE /api/users/me removes the user; subsequent login returns 400."""
    token, _ = await _register_and_login(client, "gone@test.com")

    resp = await client.delete(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Can no longer log in
    login_resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": "gone@test.com", "password": "pass123"},
    )
    assert login_resp.status_code == 400


async def test_delete_me_sets_analyses_user_id_to_null(client):
    """Deleting a user sets their analyses' user_id to NULL via ON DELETE SET NULL."""
    token, user_id = await _register_and_login(client, "orphan@test.com")
    analysis_id = await _seed_analysis_for_user(user_id)

    resp = await client.delete(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # The analysis should still exist with user_id=NULL
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(select(Analysis).where(Analysis.id == analysis_id))
        analysis = result.scalar_one_or_none()
    assert analysis is not None
    assert analysis.user_id is None
