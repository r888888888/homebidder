"""
Tests for user registration, login, and /me endpoints (fastapi-users).
Written before implementation (TDD).
"""
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

async def test_register_creates_user(client):
    """POST /api/auth/register with valid creds returns 201 with user data."""
    resp = await client.post("/api/auth/register", json={
        "email": "newuser@example.com",
        "password": "securepass123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "hashed_password" not in data  # never exposed


async def test_register_duplicate_email_returns_400(client):
    """Registering with an already-used email returns 400."""
    payload = {"email": "dup@example.com", "password": "pass123"}
    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 400


async def test_register_missing_email_returns_422(client):
    """Registration without email returns 422 validation error."""
    resp = await client.post("/api/auth/register", json={"password": "pass123"})
    assert resp.status_code == 422


async def test_register_missing_password_returns_422(client):
    """Registration without password returns 422 validation error."""
    resp = await client.post("/api/auth/register", json={"email": "nopw@example.com"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------

async def test_login_returns_access_token(client):
    """POST /api/auth/jwt/login with correct credentials returns an access_token."""
    await client.post("/api/auth/register", json={"email": "login@example.com", "password": "pass123"})
    resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": "login@example.com", "password": "pass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password_returns_400(client):
    """Login with the wrong password returns 400."""
    await client.post("/api/auth/register", json={"email": "wrong@example.com", "password": "pass123"})
    resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": "wrong@example.com", "password": "badpassword"},
    )
    assert resp.status_code == 400


async def test_login_nonexistent_user_returns_400(client):
    """Login for an account that does not exist returns 400."""
    resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": "ghost@example.com", "password": "pass123"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /api/users/me
# ---------------------------------------------------------------------------

async def test_me_returns_user_when_authenticated(client):
    """GET /api/users/me returns the current user's data with a valid Bearer token."""
    await client.post("/api/auth/register", json={"email": "me@example.com", "password": "pass123"})
    login_resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": "me@example.com", "password": "pass123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "me@example.com"
    assert "id" in data
    assert "hashed_password" not in data


async def test_me_returns_401_when_unauthenticated(client):
    """GET /api/users/me without a token returns 401."""
    resp = await client.get("/api/users/me")
    assert resp.status_code == 401


async def test_me_returns_401_with_invalid_token(client):
    """GET /api/users/me with a garbage token returns 401."""
    resp = await client.get("/api/users/me", headers={"Authorization": "Bearer notavalidtoken"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Regression: analyze still works unauthenticated
# ---------------------------------------------------------------------------

async def _mock_run_agent(address, buyer_context="", db=None, force_refresh=False, user_id=None):
    import json
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def test_analyze_still_works_unauthenticated(client):
    """POST /api/analyze without a token still returns 200 (auth is optional)."""
    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post("/api/analyze", json={
            "address": "450 Sanchez St, San Francisco, CA 94114",
        })
    assert resp.status_code == 200


async def test_analyze_still_works_authenticated(client):
    """POST /api/analyze with a valid Bearer token also returns 200."""
    await client.post("/api/auth/register", json={"email": "analyzer@example.com", "password": "pass123"})
    login_resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": "analyzer@example.com", "password": "pass123"},
    )
    token = login_resp.json()["access_token"]

    with patch("api.routes.run_agent", _mock_run_agent):
        resp = await client.post(
            "/api/analyze",
            json={"address": "450 Sanchez St, San Francisco, CA 94114"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
