"""Tests for the HTTP-Basic-Auth protected admin portal endpoints.

Written before implementation (TDD red phase).
"""
import base64


ADMIN_USER = "admin"
ADMIN_PASS = "testadminpass"  # must match conftest.py os.environ.setdefault


def _basic_auth(user: str, password: str) -> str:
    creds = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {creds}"


# ---------------------------------------------------------------------------
# Users endpoint
# ---------------------------------------------------------------------------


async def test_admin_users_no_auth_returns_401(client):
    """GET /api/admin/users without credentials returns 401."""
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


async def test_admin_users_wrong_password_returns_401(client):
    """GET /api/admin/users with wrong password returns 401."""
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth(ADMIN_USER, "wrongpass")},
    )
    assert resp.status_code == 401


async def test_admin_users_correct_auth_returns_list(client):
    """GET /api/admin/users with correct credentials returns the user list."""
    await client.post(
        "/api/auth/register",
        json={"email": "admintest@example.com", "password": "pass123"},
    )
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(u["email"] == "admintest@example.com" for u in data)


async def test_admin_users_response_never_exposes_hashed_password(client):
    """The users response must not include hashed_password."""
    await client.post(
        "/api/auth/register",
        json={"email": "noleak@example.com", "password": "pass123"},
    )
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    assert resp.status_code == 200
    for user in resp.json():
        assert "hashed_password" not in user


async def test_admin_users_response_has_expected_fields(client):
    """Each user object has id, email, is_active, is_verified, is_superuser."""
    await client.post(
        "/api/auth/register",
        json={"email": "fields@example.com", "password": "pass123"},
    )
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    assert resp.status_code == 200
    user = next(u for u in resp.json() if u["email"] == "fields@example.com")
    for field in ("id", "email", "is_active", "is_verified", "is_superuser"):
        assert field in user, f"missing field: {field}"


async def test_admin_users_empty_when_no_users(client):
    """Returns an empty list when no users are registered."""
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Analyses endpoint
# ---------------------------------------------------------------------------


async def test_admin_analyses_no_auth_returns_401(client):
    """GET /api/admin/analyses without credentials returns 401."""
    resp = await client.get("/api/admin/analyses")
    assert resp.status_code == 401


async def test_admin_analyses_correct_auth_returns_list(client):
    """GET /api/admin/analyses with correct credentials returns a list."""
    resp = await client.get(
        "/api/admin/analyses",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Not-configured guard
# ---------------------------------------------------------------------------


async def test_admin_not_configured_returns_503(client, monkeypatch):
    """When ADMIN_PASSWORD is not set, endpoints return 503."""
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth("admin", "anypass")},
    )
    assert resp.status_code == 503
