import datetime
import hashlib
import os
from unittest.mock import patch

from db import engine
from db.models import RateLimitEntry
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker


async def _mock_run_agent(address, buyer_context="", db=None, force_refresh=False, user_id=None):
    import json
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


async def _seed_entries(ip: str, count: int, hours_ago: float = 1.0) -> None:
    """Seed RateLimitEntry rows for a given IP at a given age."""
    identifier = _hash_ip(ip)
    ts = datetime.datetime.utcnow() - datetime.timedelta(hours=hours_ago)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        for _ in range(count):
            session.add(RateLimitEntry(identifier=identifier, created_at=ts))
        await session.commit()


async def _seed_entries_for_identifier(identifier: str, count: int, hours_ago: float = 1.0) -> None:
    """Seed RateLimitEntry rows for an arbitrary identifier string (e.g. a user UUID)."""
    ts = datetime.datetime.utcnow() - datetime.timedelta(hours=hours_ago)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        for _ in range(count):
            session.add(RateLimitEntry(identifier=identifier, created_at=ts))
        await session.commit()


# ---------------------------------------------------------------------------
# /api/analyze rate limiting
# ---------------------------------------------------------------------------

async def test_rate_limit_allows_requests_under_limit(client):
    """First 5 requests from the same IP all succeed."""
    with patch("api.routes.run_agent", _mock_run_agent):
        for _ in range(5):
            resp = await client.post(
                "/api/analyze",
                json={"address": "450 Sanchez St, SF, CA 94114"},
                headers={"Fly-Client-IP": "10.0.0.1"},
            )
            assert resp.status_code == 200


async def test_rate_limit_blocks_sixth_request(client):
    """6th request from the same IP within 24 h returns 429 with Retry-After."""
    await _seed_entries("10.0.0.2", count=5)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Fly-Client-IP": "10.0.0.2"},
        )
    assert resp.status_code == 429
    assert "retry-after" in resp.headers


async def test_rate_limit_old_entries_dont_count(client):
    """Entries older than 24 h are outside the window and don't count."""
    await _seed_entries("10.0.0.3", count=5, hours_ago=25)

    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Fly-Client-IP": "10.0.0.3"},
        )
    assert resp.status_code == 200


async def test_rate_limit_different_ips_tracked_separately(client):
    """Exhausting one IP's quota doesn't affect a different IP."""
    await _seed_entries("10.0.0.4", count=5)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Fly-Client-IP": "10.0.0.5"},  # different IP
        )
    assert resp.status_code == 200


async def test_rate_limit_disabled_allows_unlimited(client):
    """When RATE_LIMIT_ENABLED=false requests are not limited."""
    import os
    await _seed_entries("10.0.0.6", count=5)
    with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "false"}):
        with patch("api.routes.run_agent", _mock_run_agent):
            resp = await client.post(
                "/api/analyze",
                json={"address": "450 Sanchez St, SF, CA 94114"},
                headers={"Fly-Client-IP": "10.0.0.6"},
            )
            assert resp.status_code == 200


async def test_identifier_prefers_fly_client_ip_over_x_forwarded_for(client):
    """Fly-Client-IP takes precedence over X-Forwarded-For."""
    await _seed_entries("10.0.0.7", count=5)  # exhaust limit for Fly IP

    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={
                "Fly-Client-IP": "10.0.0.7",
                "X-Forwarded-For": "10.0.0.8",  # fresh IP — should be ignored
            },
        )
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# GET /api/rate-limit/status
# ---------------------------------------------------------------------------

async def test_status_full_quota_when_no_prior_requests(client):
    """Fresh identifier returns full remaining quota and null reset_at."""
    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Fly-Client-IP": "7.7.7.7"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["used"] == 0
    assert data["limit"] == 5
    assert data["remaining"] == 5
    assert data["reset_at"] is None


async def test_status_returns_correct_remaining(client):
    """After 3 analyses the status reports used=3 remaining=2."""
    await _seed_entries("9.9.9.9", count=3)

    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Fly-Client-IP": "9.9.9.9"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["used"] == 3
    assert data["limit"] == 5
    assert data["remaining"] == 2
    assert data["reset_at"] is not None


async def test_status_zero_remaining_at_limit(client):
    """When limit is exhausted remaining=0 and reset_at is set."""
    await _seed_entries("8.8.8.8", count=5)

    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Fly-Client-IP": "8.8.8.8"},
    )
    data = resp.json()
    assert data["remaining"] == 0
    assert data["reset_at"] is not None


async def test_status_old_entries_excluded_from_count(client):
    """Entries older than 24 h are not counted in the status response."""
    await _seed_entries("6.6.6.6", count=5, hours_ago=25)

    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Fly-Client-IP": "6.6.6.6"},
    )
    data = resp.json()
    assert data["used"] == 0
    assert data["remaining"] == 5


# ---------------------------------------------------------------------------
# Authenticated user rate limiting
# ---------------------------------------------------------------------------

async def test_authenticated_user_not_blocked_by_ip_limit(client):
    """An authenticated user is not blocked by the IP-based limit."""
    # Register + login
    await client.post("/api/auth/register", json={"email": "auth_rl1@test.com", "password": "pass123"})
    login_resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": "auth_rl1@test.com", "password": "pass123"},
    )
    token = login_resp.json()["access_token"]

    # Exhaust the IP-based limit for 10.0.100.1
    await _seed_entries("10.0.100.1", count=5)

    # The authenticated user should still be allowed (uses account quota, not IP quota)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={
                "Fly-Client-IP": "10.0.100.1",
                "Authorization": f"Bearer {token}",
            },
        )
    assert resp.status_code == 200


async def test_authenticated_user_limited_by_account_quota(client):
    """An authenticated user is blocked when their own account quota is exhausted."""
    with patch.dict(os.environ, {"RATE_LIMIT_AUTHENTICATED_PER_DAY": "3"}):
        await client.post("/api/auth/register", json={"email": "auth_rl2@test.com", "password": "pass123"})
        login_resp = await client.post(
            "/api/auth/jwt/login",
            data={"username": "auth_rl2@test.com", "password": "pass123"},
        )
        token = login_resp.json()["access_token"]
        user_id = (await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})).json()["id"]

        # Exhaust the account quota
        await _seed_entries_for_identifier(user_id, count=3)

        with patch("api.routes.run_agent", _mock_run_agent):
            resp = await client.post(
                "/api/analyze",
                json={"address": "450 Sanchez St, SF, CA 94114"},
                headers={"Authorization": f"Bearer {token}"},
            )
    assert resp.status_code == 429


async def test_authenticated_uses_user_id_not_ip(client):
    """Two authenticated users from the same IP each have independent quotas."""
    with patch.dict(os.environ, {"RATE_LIMIT_AUTHENTICATED_PER_DAY": "3"}):
        # Register two users
        await client.post("/api/auth/register", json={"email": "ua1@test.com", "password": "pass123"})
        await client.post("/api/auth/register", json={"email": "ua2@test.com", "password": "pass123"})

        login1 = await client.post("/api/auth/jwt/login", data={"username": "ua1@test.com", "password": "pass123"})
        login2 = await client.post("/api/auth/jwt/login", data={"username": "ua2@test.com", "password": "pass123"})
        token1 = login1.json()["access_token"]
        token2 = login2.json()["access_token"]
        user1_id = (await client.get("/api/users/me", headers={"Authorization": f"Bearer {token1}"})).json()["id"]

        # Exhaust user1's quota
        await _seed_entries_for_identifier(user1_id, count=3)

        # user2 from the same IP should still succeed
        with patch("api.routes.run_agent", _mock_run_agent):
            resp = await client.post(
                "/api/analyze",
                json={"address": "450 Sanchez St, SF, CA 94114"},
                headers={
                    "Fly-Client-IP": "10.0.100.2",
                    "Authorization": f"Bearer {token2}",
                },
            )
    assert resp.status_code == 200
