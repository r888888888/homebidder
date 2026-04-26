"""
Tests for the core rate-limiting infrastructure:
- IP identification (Fly-Client-IP header priority)
- Anonymous monthly window via RateLimitEntry
- RATE_LIMIT_ENABLED=false bypass
- GET /api/rate-limit/status

Tier-specific limit tests (buyer/investor/agent/superuser) live in
test_payments_rate_limit.py.
"""
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


async def _seed_entries(ip: str, count: int, days_ago: float = 0.0) -> None:
    """Seed RateLimitEntry rows for a given IP at a given age (days)."""
    identifier = _hash_ip(ip)
    ts = datetime.datetime.utcnow() - datetime.timedelta(days=days_ago)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        for _ in range(count):
            session.add(RateLimitEntry(identifier=identifier, created_at=ts))
        await session.commit()


# ---------------------------------------------------------------------------
# /api/analyze — anonymous monthly limit (3/month)
# ---------------------------------------------------------------------------

async def test_rate_limit_allows_requests_under_limit(client):
    """First 3 requests from the same IP this month succeed."""
    with patch("api.routes.run_agent", _mock_run_agent):
        for _ in range(3):
            resp = await client.post(
                "/api/analyze",
                json={"address": "450 Sanchez St, SF, CA 94114"},
                headers={"Fly-Client-IP": "10.0.0.1"},
            )
            assert resp.status_code == 200


async def test_rate_limit_blocks_fourth_request(client):
    """4th request from the same IP within the month returns 429."""
    await _seed_entries("10.0.0.2", count=3)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Fly-Client-IP": "10.0.0.2"},
        )
    assert resp.status_code == 429
    assert "retry-after" in resp.headers


async def test_rate_limit_old_entries_dont_count(client):
    """Entries from the previous month are outside the window and don't count."""
    await _seed_entries("10.0.0.3", count=3, days_ago=35)  # prior month

    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Fly-Client-IP": "10.0.0.3"},
        )
    assert resp.status_code == 200


async def test_rate_limit_different_ips_tracked_separately(client):
    """Exhausting one IP's quota doesn't affect a different IP."""
    await _seed_entries("10.0.0.4", count=3)
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, SF, CA 94114"},
            headers={"Fly-Client-IP": "10.0.0.5"},  # different IP
        )
    assert resp.status_code == 200


async def test_rate_limit_disabled_allows_unlimited(client):
    """When RATE_LIMIT_ENABLED=false requests are not limited."""
    await _seed_entries("10.0.0.6", count=3)
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
    await _seed_entries("10.0.0.7", count=3)  # exhaust limit for Fly IP

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


async def test_authenticated_user_not_blocked_by_ip_limit(client):
    """An authenticated user is not blocked by the IP-based anonymous limit."""
    await client.post("/api/auth/register", json={"email": "auth_rl1@test.com", "password": "pass123"})
    login_resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": "auth_rl1@test.com", "password": "pass123"},
    )
    token = login_resp.json()["access_token"]

    # Exhaust the IP-based limit
    await _seed_entries("10.0.100.1", count=3)

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


# ---------------------------------------------------------------------------
# GET /api/rate-limit/status
# ---------------------------------------------------------------------------

async def test_status_full_quota_when_no_prior_requests(client):
    """Fresh anonymous identifier returns full remaining quota."""
    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Fly-Client-IP": "7.7.7.7"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["used"] == 0
    assert data["limit"] == 3
    assert data["remaining"] == 3
    assert data["window"] == "monthly"
    assert data["tier"] == "anonymous"


async def test_status_returns_correct_remaining(client):
    """After 2 analyses the status reports used=2 remaining=1."""
    await _seed_entries("9.9.9.9", count=2)

    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Fly-Client-IP": "9.9.9.9"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["used"] == 2
    assert data["limit"] == 3
    assert data["remaining"] == 1
    assert data["reset_at"] is not None


async def test_status_zero_remaining_at_limit(client):
    """When limit is exhausted remaining=0."""
    await _seed_entries("8.8.8.8", count=3)

    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Fly-Client-IP": "8.8.8.8"},
    )
    data = resp.json()
    assert data["remaining"] == 0


async def test_status_old_entries_excluded_from_count(client):
    """Entries from the previous month are not counted in status."""
    await _seed_entries("6.6.6.6", count=3, days_ago=35)

    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Fly-Client-IP": "6.6.6.6"},
    )
    data = resp.json()
    assert data["used"] == 0
    assert data["remaining"] == 3


async def test_status_authenticated_user_sees_buyer_limit(client):
    """Logged-in Buyer user sees the 5-analysis monthly limit."""
    await client.post("/api/auth/register", json={"email": "status_auth1@test.com", "password": "pass123"})
    login_resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": "status_auth1@test.com", "password": "pass123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.get(
        "/api/rate-limit/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 5
    assert data["used"] == 0
    assert data["remaining"] == 5
    assert data["window"] == "monthly"
    assert data["tier"] == "buyer"
