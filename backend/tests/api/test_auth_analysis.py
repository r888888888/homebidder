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


# ---------------------------------------------------------------------------
# Retention limit helpers
# ---------------------------------------------------------------------------

async def _seed_analysis_at(user_id, address: str, days_ago: int) -> int:
    """Seed a Listing + Analysis with created_at = now - days_ago days."""
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
            session_id="retention-session",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=days_ago),
            user_id=user_id,
        )
        session.add(analysis)
        await session.commit()
        return analysis.id


async def _set_user_tier(user_id_str: str, tier: str) -> None:
    """Directly update a user's subscription_tier in the DB."""
    import uuid as uuid_mod
    from db.models import User as UserModel
    from sqlalchemy import update

    uid = uuid_mod.UUID(user_id_str)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(
            update(UserModel).where(UserModel.id == uid).values(subscription_tier=tier)
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Retention limit tests
# ---------------------------------------------------------------------------

async def test_buyer_retention_hides_analyses_older_than_30_days(client):
    """Buyer tier: analyses older than 30 days are excluded from the list."""
    import uuid as uuid_mod

    token, user_id = await _register_and_login(client, "buyer_retention@test.com")
    uid = uuid_mod.UUID(user_id)
    # subscription_tier defaults to 'buyer' on registration — no tier update needed

    await _seed_analysis_at(uid, "10 Recent St, SF, CA 94110", days_ago=10)
    await _seed_analysis_at(uid, "40 Old St, SF, CA 94110", days_ago=40)

    resp = await client.get("/api/analyses", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert "10 RECENT ST" in data["items"][0]["address"]


async def test_buyer_retention_shows_analyses_within_30_days(client):
    """Buyer tier: analyses within the last 30 days are visible."""
    import uuid as uuid_mod

    token, user_id = await _register_and_login(client, "buyer_recent@test.com")
    uid = uuid_mod.UUID(user_id)

    await _seed_analysis_at(uid, "1 Fresh St, SF, CA 94110", days_ago=1)

    resp = await client.get("/api/analyses", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


async def test_investor_retention_hides_analyses_older_than_180_days(client):
    """Investor tier: analyses older than 180 days are excluded; within 180 days are shown."""
    import uuid as uuid_mod

    token, user_id = await _register_and_login(client, "investor_retention@test.com")
    uid = uuid_mod.UUID(user_id)
    await _set_user_tier(user_id, "investor")

    await _seed_analysis_at(uid, "10 Inv Recent St, SF, CA 94110", days_ago=10)
    await _seed_analysis_at(uid, "100 Inv Mid St, SF, CA 94110", days_ago=100)
    await _seed_analysis_at(uid, "200 Inv Old St, SF, CA 94110", days_ago=200)

    resp = await client.get("/api/analyses", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    addresses = [item["address"] for item in data["items"]]
    assert any("10 INV RECENT" in a for a in addresses)
    assert any("100 INV MID" in a for a in addresses)
    assert not any("200 INV OLD" in a for a in addresses)


async def test_agent_no_retention_limit(client):
    """Agent tier: all analyses are visible regardless of age."""
    import uuid as uuid_mod

    token, user_id = await _register_and_login(client, "agent_retention@test.com")
    uid = uuid_mod.UUID(user_id)
    await _set_user_tier(user_id, "agent")

    await _seed_analysis_at(uid, "10 Agt Recent St, SF, CA 94110", days_ago=10)
    await _seed_analysis_at(uid, "100 Agt Mid St, SF, CA 94110", days_ago=100)
    await _seed_analysis_at(uid, "400 Agt Old St, SF, CA 94110", days_ago=400)

    resp = await client.get("/api/analyses", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3


# ---------------------------------------------------------------------------
# Favorite toggle
# ---------------------------------------------------------------------------

async def test_toggle_favorite_own_analysis_sets_is_favorite(client):
    """PATCH /api/analyses/{id}/favorite toggles is_favorite for the owning user."""
    import uuid as uuid_mod

    token, user_id = await _register_and_login(client, "fav_user@test.com")
    uid = uuid_mod.UUID(user_id)
    analysis_id = await _seed_analysis(user_id=uid, address="1 Fav St, SF, CA 94110")

    resp = await client.patch(
        f"/api/analyses/{analysis_id}/favorite",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_favorite"] is True


async def test_toggle_favorite_twice_resets_to_false(client):
    """PATCH /api/analyses/{id}/favorite twice toggles back to is_favorite=False."""
    import uuid as uuid_mod

    token, user_id = await _register_and_login(client, "fav_toggle@test.com")
    uid = uuid_mod.UUID(user_id)
    analysis_id = await _seed_analysis(user_id=uid, address="2 Fav St, SF, CA 94110")

    await client.patch(
        f"/api/analyses/{analysis_id}/favorite",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.patch(
        f"/api/analyses/{analysis_id}/favorite",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_favorite"] is False


async def test_toggle_favorite_reflects_in_list(client):
    """After toggling favorite, GET /api/analyses includes is_favorite=True for that item."""
    import uuid as uuid_mod

    token, user_id = await _register_and_login(client, "fav_list@test.com")
    uid = uuid_mod.UUID(user_id)
    analysis_id = await _seed_analysis(user_id=uid, address="3 Fav St, SF, CA 94110")

    await client.patch(
        f"/api/analyses/{analysis_id}/favorite",
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get("/api/analyses", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["is_favorite"] is True


async def test_toggle_favorite_other_user_returns_403(client):
    """PATCH /api/analyses/{id}/favorite by a different user returns 403."""
    import uuid as uuid_mod

    _, user_a_id = await _register_and_login(client, "fav_owner@test.com")
    uid_a = uuid_mod.UUID(user_a_id)
    analysis_id = await _seed_analysis(user_id=uid_a, address="4 Fav St, SF, CA 94110")

    token_b, _ = await _register_and_login(client, "fav_thief@test.com")
    resp = await client.patch(
        f"/api/analyses/{analysis_id}/favorite",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


async def test_toggle_favorite_not_found_returns_404(client):
    """PATCH /api/analyses/99999/favorite returns 404."""
    token, _ = await _register_and_login(client, "fav_404@test.com")
    resp = await client.patch(
        "/api/analyses/99999/favorite",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
