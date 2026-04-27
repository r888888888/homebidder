"""
Phase 2 tests: analyses tied to the logged-in user.

Covers:
- analyze with auth sets user_id on the Analysis
- analyze without auth leaves user_id NULL
- list_analyses authenticated returns only own analyses
- list_analyses unauthenticated returns only anonymous analyses
- delete own analysis succeeds 204
- delete someone else's analysis returns 403
"""
import datetime
import json
from unittest.mock import patch

from db import engine
from db.models import Analysis, Listing
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_analysis(user_id=None, address="1 Seed St, SF, CA 94110") -> int:
    """Directly insert a Listing + Analysis row and return the analysis id."""
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


async def _mock_run_agent_with_analysis_id(address, buyer_context="", db=None, force_refresh=False, user_id=None):
    """Mock that always yields an analysis_id event with id=1."""
    yield f"data: {json.dumps({'type': 'analysis_id', 'id': 1})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def _mock_run_agent(address, buyer_context="", db=None, force_refresh=False, user_id=None):
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ---------------------------------------------------------------------------
# user_id set / not-set on analysis
# ---------------------------------------------------------------------------

async def test_analyze_with_auth_sets_user_id(client):
    """When an authenticated user runs /api/analyze, the Analysis.user_id is their UUID."""
    import uuid
    from sqlalchemy import select

    token, user_id = await _register_and_login(client, "authed_analyzer@test.com")

    # Track the user_id passed into run_agent
    captured_user_id = []

    async def _capturing_mock(address, buyer_context="", db=None, force_refresh=False, user_id=None):
        captured_user_id.append(user_id)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    with patch("api.routes.run_agent", _capturing_mock):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, San Francisco, CA 94114"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert len(captured_user_id) == 1
    # The user_id passed to run_agent must be the authenticated user's UUID
    assert str(captured_user_id[0]) == user_id


async def test_analyze_without_auth_passes_none_user_id(client):
    """When an unauthenticated request runs /api/analyze, user_id passed to run_agent is None."""
    captured_user_id = []

    async def _capturing_mock(address, buyer_context="", db=None, force_refresh=False, user_id=None):
        captured_user_id.append(user_id)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    with patch("api.routes.run_agent", _capturing_mock):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, San Francisco, CA 94114"},
        )

    assert resp.status_code == 200
    assert captured_user_id[0] is None


# ---------------------------------------------------------------------------
# list_analyses scoping
# ---------------------------------------------------------------------------

async def test_list_analyses_authenticated_returns_only_own(client):
    """GET /api/analyses with auth returns only analyses belonging to that user."""
    import uuid as uuid_mod

    token, user_id = await _register_and_login(client, "lister@test.com")
    uid = uuid_mod.UUID(user_id)

    # Seed one analysis for this user, one anonymous
    await _seed_analysis(user_id=uid, address="1 Own St, SF, CA 94110")
    await _seed_analysis(user_id=None, address="2 Anon St, SF, CA 94110")

    resp = await client.get("/api/analyses", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["address"] == "1 OWN ST, SF, CA 94110"


async def test_list_analyses_unauthenticated_returns_only_anonymous(client):
    """GET /api/analyses without auth returns only analyses with user_id IS NULL."""
    import uuid as uuid_mod

    token, user_id = await _register_and_login(client, "owner2@test.com")
    uid = uuid_mod.UUID(user_id)

    await _seed_analysis(user_id=uid, address="3 Owned St, SF, CA 94110")
    await _seed_analysis(user_id=None, address="4 Public St, SF, CA 94110")

    resp = await client.get("/api/analyses")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["address"] == "4 PUBLIC ST, SF, CA 94110"


# ---------------------------------------------------------------------------
# delete ownership checks
# ---------------------------------------------------------------------------

async def test_delete_own_analysis_succeeds_204(client):
    """DELETE /api/analyses/{id} by the owning user returns 204."""
    import uuid as uuid_mod

    token, user_id = await _register_and_login(client, "deleter@test.com")
    uid = uuid_mod.UUID(user_id)

    analysis_id = await _seed_analysis(user_id=uid, address="5 Mine St, SF, CA 94110")

    resp = await client.delete(
        f"/api/analyses/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Confirm gone
    resp2 = await client.get(f"/api/analyses/{analysis_id}")
    assert resp2.status_code == 404


async def test_delete_others_analysis_returns_403(client):
    """DELETE /api/analyses/{id} by a different authenticated user returns 403."""
    import uuid as uuid_mod

    # User A creates an analysis
    _, user_a_id = await _register_and_login(client, "owner_a@test.com")
    uid_a = uuid_mod.UUID(user_a_id)
    analysis_id = await _seed_analysis(user_id=uid_a, address="6 Yours St, SF, CA 94110")

    # User B tries to delete it
    token_b, _ = await _register_and_login(client, "thief_b@test.com")
    resp = await client.delete(
        f"/api/analyses/{analysis_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


async def test_delete_anonymous_analysis_by_authed_user_returns_403(client):
    """An authenticated user cannot delete an anonymous (user_id=None) analysis."""
    token, _ = await _register_and_login(client, "grabber@test.com")
    analysis_id = await _seed_analysis(user_id=None, address="7 Nobody St, SF, CA 94110")

    resp = await client.delete(
        f"/api/analyses/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_delete_anon_analysis_without_auth_succeeds(client):
    """Anonymous users can still delete analyses that have no owner (user_id=None)."""
    analysis_id = await _seed_analysis(user_id=None, address="8 Free St, SF, CA 94110")

    resp = await client.delete(f"/api/analyses/{analysis_id}")
    assert resp.status_code == 204
