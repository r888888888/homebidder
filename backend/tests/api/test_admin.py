"""Tests for the superuser-protected admin portal endpoints.

Covers auth guards, paginated response shape, and pagination behaviour.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from db import engine
from db.models import User


async def _register_and_login(client, email: str, password: str = "pass123") -> str:
    """Register a user and return their JWT access token."""
    await client.post("/api/auth/register", json={"email": email, "password": password})
    login_resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": password},
    )
    return login_resp.json()["access_token"]


async def _make_superuser(email: str) -> None:
    """Directly set is_superuser=True for the user with the given email."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.is_superuser = True
        await session.commit()


async def _superuser_token(client, email: str = "superadmin@example.com") -> str:
    """Register a superuser and return their JWT access token."""
    token = await _register_and_login(client, email)
    await _make_superuser(email)
    return token


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


async def test_admin_users_no_auth_returns_401(client):
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


async def test_admin_analyses_no_auth_returns_401(client):
    resp = await client.get("/api/admin/analyses")
    assert resp.status_code == 401


async def test_admin_users_non_superuser_returns_403(client):
    token = await _register_and_login(client, "regular@example.com")
    resp = await client.get("/api/admin/users", headers=_bearer(token))
    assert resp.status_code == 403


async def test_admin_analyses_non_superuser_returns_403(client):
    token = await _register_and_login(client, "regular@example.com")
    resp = await client.get("/api/admin/analyses", headers=_bearer(token))
    assert resp.status_code == 403


async def test_admin_users_superuser_returns_200(client):
    token = await _superuser_token(client)
    resp = await client.get("/api/admin/users", headers=_bearer(token))
    assert resp.status_code == 200


async def test_admin_analyses_superuser_returns_200(client):
    token = await _superuser_token(client)
    resp = await client.get("/api/admin/analyses", headers=_bearer(token))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Paginated response shape
# ---------------------------------------------------------------------------


async def test_admin_users_response_has_pagination_envelope(client):
    """Response contains items, total, page, page_size, pages."""
    token = await _superuser_token(client)
    resp = await client.get("/api/admin/users", headers=_bearer(token))
    assert resp.status_code == 200
    data = resp.json()
    for key in ("items", "total", "page", "page_size", "pages"):
        assert key in data, f"missing key: {key}"
    assert isinstance(data["items"], list)


async def test_admin_users_correct_auth_returns_user_in_items(client):
    token = await _superuser_token(client)
    await _register_and_login(client, "admintest@example.com")
    resp = await client.get("/api/admin/users", headers=_bearer(token))
    assert resp.status_code == 200
    assert any(u["email"] == "admintest@example.com" for u in resp.json()["items"])


async def test_admin_users_response_never_exposes_hashed_password(client):
    token = await _superuser_token(client)
    await _register_and_login(client, "noleak@example.com")
    resp = await client.get("/api/admin/users", headers=_bearer(token))
    for user in resp.json()["items"]:
        assert "hashed_password" not in user


async def test_admin_users_response_has_expected_fields(client):
    token = await _superuser_token(client)
    await _register_and_login(client, "fields@example.com")
    resp = await client.get("/api/admin/users", headers=_bearer(token))
    user = next(u for u in resp.json()["items"] if u["email"] == "fields@example.com")
    for field in ("id", "email", "is_active", "is_verified", "is_superuser"):
        assert field in user, f"missing field: {field}"


async def test_admin_users_includes_the_superuser_itself(client):
    token = await _superuser_token(client)
    resp = await client.get("/api/admin/users", headers=_bearer(token))
    data = resp.json()
    assert data["total"] >= 1
    assert any(u["email"] == "superadmin@example.com" for u in data["items"])


async def test_admin_analyses_response_has_pagination_envelope(client):
    token = await _superuser_token(client)
    resp = await client.get("/api/admin/analyses", headers=_bearer(token))
    assert resp.status_code == 200
    data = resp.json()
    for key in ("items", "total", "page", "page_size", "pages"):
        assert key in data


# ---------------------------------------------------------------------------
# Pagination behaviour
# ---------------------------------------------------------------------------


async def _register_n_users(client, n: int) -> None:
    for i in range(n):
        await _register_and_login(client, f"paginationuser{i}@example.com")


async def test_admin_users_page_size_limits_items(client):
    """page_size=2 returns at most 2 items per page."""
    token = await _superuser_token(client)
    await _register_n_users(client, 5)
    resp = await client.get(
        "/api/admin/users?page=1&page_size=2",
        headers=_bearer(token),
    )
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 6  # 5 regular + 1 superuser
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["pages"] == 3  # ceil(6/2)


async def test_admin_users_second_page_has_different_items(client):
    """Page 2 returns a non-overlapping set of users from page 1."""
    token = await _superuser_token(client)
    await _register_n_users(client, 4)
    resp1 = await client.get(
        "/api/admin/users?page=1&page_size=2",
        headers=_bearer(token),
    )
    resp2 = await client.get(
        "/api/admin/users?page=2&page_size=2",
        headers=_bearer(token),
    )
    ids1 = {u["id"] for u in resp1.json()["items"]}
    ids2 = {u["id"] for u in resp2.json()["items"]}
    assert ids1.isdisjoint(ids2), "pages should not overlap"


async def test_admin_users_page_beyond_last_returns_empty_items(client):
    """Requesting a page past the last one returns an empty items list."""
    token = await _superuser_token(client)
    await _register_n_users(client, 2)
    resp = await client.get(
        "/api/admin/users?page=99&page_size=10",
        headers=_bearer(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 3  # 2 regular + 1 superuser


async def test_admin_analyses_page_size_query_param(client):
    """Analyses endpoint honours page_size."""
    token = await _superuser_token(client)
    resp = await client.get(
        "/api/admin/analyses?page=1&page_size=10",
        headers=_bearer(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
