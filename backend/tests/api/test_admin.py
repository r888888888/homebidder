"""Tests for the HTTP-Basic-Auth protected admin portal endpoints.

Covers auth guards, paginated response shape, and pagination behaviour.
"""
import base64

ADMIN_USER = "admin"
ADMIN_PASS = "testadminpass"  # must match conftest.py os.environ.setdefault


def _basic_auth(user: str, password: str) -> str:
    creds = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {creds}"


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


async def test_admin_users_no_auth_returns_401(client):
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


async def test_admin_users_wrong_password_returns_401(client):
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth(ADMIN_USER, "wrongpass")},
    )
    assert resp.status_code == 401


async def test_admin_analyses_no_auth_returns_401(client):
    resp = await client.get("/api/admin/analyses")
    assert resp.status_code == 401


async def test_admin_not_configured_returns_503(client, monkeypatch):
    """When ADMIN_PASSWORD is not set, endpoints return 503."""
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth("admin", "anypass")},
    )
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Paginated response shape
# ---------------------------------------------------------------------------


async def test_admin_users_response_has_pagination_envelope(client):
    """Response contains items, total, page, page_size, pages."""
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in ("items", "total", "page", "page_size", "pages"):
        assert key in data, f"missing key: {key}"
    assert isinstance(data["items"], list)


async def test_admin_users_correct_auth_returns_user_in_items(client):
    await client.post(
        "/api/auth/register",
        json={"email": "admintest@example.com", "password": "pass123"},
    )
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    assert resp.status_code == 200
    assert any(u["email"] == "admintest@example.com" for u in resp.json()["items"])


async def test_admin_users_response_never_exposes_hashed_password(client):
    await client.post(
        "/api/auth/register",
        json={"email": "noleak@example.com", "password": "pass123"},
    )
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    for user in resp.json()["items"]:
        assert "hashed_password" not in user


async def test_admin_users_response_has_expected_fields(client):
    await client.post(
        "/api/auth/register",
        json={"email": "fields@example.com", "password": "pass123"},
    )
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    user = next(u for u in resp.json()["items"] if u["email"] == "fields@example.com")
    for field in ("id", "email", "is_active", "is_verified", "is_superuser"):
        assert field in user, f"missing field: {field}"


async def test_admin_users_empty_returns_zero_total(client):
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_admin_analyses_response_has_pagination_envelope(client):
    resp = await client.get(
        "/api/admin/analyses",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in ("items", "total", "page", "page_size", "pages"):
        assert key in data


# ---------------------------------------------------------------------------
# Pagination behaviour
# ---------------------------------------------------------------------------


async def _register_n_users(client, n: int):
    for i in range(n):
        await client.post(
            "/api/auth/register",
            json={"email": f"paginationuser{i}@example.com", "password": "pass123"},
        )


async def test_admin_users_page_size_limits_items(client):
    """page_size=2 returns at most 2 items per page."""
    await _register_n_users(client, 5)
    resp = await client.get(
        "/api/admin/users?page=1&page_size=2",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["pages"] == 3  # ceil(5/2)


async def test_admin_users_second_page_has_different_items(client):
    """Page 2 returns a non-overlapping set of users from page 1."""
    await _register_n_users(client, 4)
    resp1 = await client.get(
        "/api/admin/users?page=1&page_size=2",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    resp2 = await client.get(
        "/api/admin/users?page=2&page_size=2",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    ids1 = {u["id"] for u in resp1.json()["items"]}
    ids2 = {u["id"] for u in resp2.json()["items"]}
    assert ids1.isdisjoint(ids2), "pages should not overlap"


async def test_admin_users_page_beyond_last_returns_empty_items(client):
    """Requesting a page past the last one returns an empty items list."""
    await _register_n_users(client, 2)
    resp = await client.get(
        "/api/admin/users?page=99&page_size=10",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 2  # total unchanged


async def test_admin_analyses_page_size_query_param(client):
    """Analyses endpoint honours page_size."""
    resp = await client.get(
        "/api/admin/analyses?page=1&page_size=10",
        headers={"Authorization": _basic_auth(ADMIN_USER, ADMIN_PASS)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
