"""Tests for affordability profile fields on /api/users/me."""


async def _register_and_login(client, email: str, password: str = "pass123"):
    await client.post("/api/auth/register", json={"email": email, "password": password})
    resp = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": password},
    )
    return resp.json()["access_token"]


async def test_get_me_returns_null_affordability_fields_by_default(client):
    token = await _register_and_login(client, "aff1@test.com")
    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "annual_income" in data
    assert data["annual_income"] is None
    assert data["monthly_debts"] is None
    assert data["down_payment"] is None
    assert data["target_rate_pct"] is None


async def test_patch_me_saves_affordability_fields(client):
    token = await _register_and_login(client, "aff2@test.com")
    resp = await client.patch(
        "/api/users/me",
        json={
            "annual_income": 150000.0,
            "monthly_debts": 500.0,
            "down_payment": 200000.0,
            "target_rate_pct": 6.75,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["annual_income"] == 150000.0
    assert data["monthly_debts"] == 500.0
    assert data["down_payment"] == 200000.0
    assert data["target_rate_pct"] == 6.75


async def test_patch_me_affordability_persists_across_requests(client):
    token = await _register_and_login(client, "aff3@test.com")
    await client.patch(
        "/api/users/me",
        json={"annual_income": 200000.0, "monthly_debts": 1000.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["annual_income"] == 200000.0
    assert data["monthly_debts"] == 1000.0
